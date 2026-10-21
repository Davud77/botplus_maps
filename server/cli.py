"""Operator tools: python -m server.cli --help. No web/DB startup side effects."""
import argparse
import json
import sys
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Botplus Maps: local, offline data preparation tools")
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect-raster", help="Inspect GeoTIFF headers and CRS without uploading or reading pixel arrays")
    inspect.add_argument("path", type=Path)
    crs = inspect.add_mutually_exclusive_group()
    crs.add_argument("--source-crs", help="Explicit source CRS: EPSG code, WKT or PROJ definition")
    crs.add_argument("--crs-file", type=Path, help="Local UTF-8 WKT/PRJ file defining source coordinates")
    for name,help_text in [('import-raster','Register a server-local raster without uploading it'),('jobs','List durable import jobs'),('job','Inspect, cancel or retry an import job'),('sources','List configured source IDs')]:
        command=commands.add_parser(name,help=help_text)
        command.add_argument('--server',default='http://localhost:5580')
        command.add_argument('--username',required=True)
        if name=='import-raster':
            command.add_argument('root',help='Configured server source ID')
            command.add_argument('path',help='Relative path inside that server source')
            command.add_argument('--title',default='')
            command.add_argument('--source-crs-id',help='Explicit source CRS override from the server catalog')
            command.add_argument('--idempotency-key')
            command.add_argument('--wait',action='store_true')
        if name=='job':
            command.add_argument('id')
            command.add_argument('--action',choices=['cancel','retry'])
    args = parser.parse_args(argv)
    try:
        if args.command!='inspect-raster':
            from .import_client import run
            return run(args)
        from .geo.raster import inspect_raster
        definition = args.crs_file.read_text(encoding="utf-8-sig") if args.crs_file else args.source_crs
        result = inspect_raster(args.path, source_crs=definition)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"Inspection failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
