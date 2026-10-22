#!/usr/bin/env python3
"""Copy legacy S3 objects to managed files; never delete or overwrite source data.

Run with the previous application image (it contains the MinIO Python SDK), with
app/worker stopped. Dry-run is the default. No credentials are printed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))
from storage import FileStorage


def digest(stream):
    result = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
        result.update(chunk)
    return result.hexdigest()


def migrate(client, root, *, apply=False, buckets=None):
    totals = {'objects': 0, 'bytes': 0, 'copied': 0, 'verified': 0, 'dry_run': not apply}
    buckets = buckets or {'panoramas': 'panoramas', 'orthophotos': 'orthophotos'}
    for bucket, namespace in buckets.items():
        if not client.bucket_exists(bucket):
            continue
        store = FileStorage(Path(root) / namespace)
        for item in client.list_objects(bucket, recursive=True):
            target = store.path(item.object_name)
            totals['objects'] += 1
            totals['bytes'] += item.size
            if not apply:
                continue
            # Hash the source and destination independently. A key with different
            # content is an error, never an instruction to replace a NAS file.
            response = client.get_object(bucket, item.object_name)
            try:
                source_hash = digest(response)
            finally:
                response.close()
                response.release_conn()
            if not target.exists():
                response = client.get_object(bucket, item.object_name)
                try:
                    store.save_file(response, item.object_name)
                finally:
                    response.close()
                    response.release_conn()
                totals['copied'] += 1
            with target.open('rb') as stream:
                target_hash = digest(stream)
            if target.stat().st_size != item.size or source_hash != target_hash:
                raise ValueError('Migration verification failed; source retained. Check the stopped writers and destination.')
            totals['verified'] += 1
    return totals


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True, type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    from minio import Minio  # Migration-only dependency, absent from the new runtime.
    client = Minio(os.environ['MINIO_ENDPOINT'],
                   access_key=os.environ['MINIO_ACCESS_KEY'],
                   secret_key=os.environ['MINIO_SECRET_KEY'],
                   secure=os.environ.get('MINIO_SECURE', 'false').lower() == 'true')
    buckets = {os.environ.get('MINIO_BUCKET_NAME', 'panoramas'): 'panoramas',
               os.environ.get('MINIO_ORTHO_BUCKET', 'orthophotos'): 'orthophotos'}
    print(json.dumps(migrate(client, args.target, apply=args.apply, buckets=buckets)))


if __name__ == '__main__':
    main()
