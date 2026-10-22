"""Associate a previously verified NAS manifest with catalog IDs; no file copies."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
from database import Database
import import_jobs
from media_worker import source_path,signature
from services.media_metadata import read_media_metadata


def main():
    parser=argparse.ArgumentParser();parser.add_argument('manifest',type=Path);parser.add_argument('--root',required=True);args=parser.parse_args();rows=json.loads(args.manifest.read_text());count=0
    for row in rows:
        try:
            root,path=source_path(args.root,row['key']);fp=import_jobs.fingerprint(path)
            if fp!=row['source_fingerprint']:continue
            meta=read_media_metadata(path)
            with Database().cursor(write=True) as c:
                c.execute('SELECT filename FROM public.photos_4326 WHERE id=%s',(row['id'],));record=c.fetchone()
                if not record or record['filename']!=row['filename']:continue
                c.execute('INSERT INTO media_import_sources(signature,photo_id) VALUES (%s,%s) ON CONFLICT DO NOTHING',(signature(args.root,row['key'],fp),row['id']))
                c.execute('UPDATE public.photos_4326 SET media_type=%s,width=%s,height=%s WHERE id=%s',(meta['media_type'],meta['width'],meta['height'],row['id']))
            count+=1
        except (ValueError,OSError):continue
    print(json.dumps({'associated_sources':count}))


if __name__=='__main__':main()
