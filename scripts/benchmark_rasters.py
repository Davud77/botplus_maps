"""Authenticated raster viewport benchmark. Never logs credentials or file paths.

Run inside the app container with --operator, or use --username from a client.
Reports contain private layer extents/tile coordinates: keep output private.
"""
import argparse
import concurrent.futures
import datetime
import getpass
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import sys
import threading
import time
import requests
from urllib.parse import urlsplit


def percentile(values,fraction):
    values=sorted(values)
    return values[max(0,math.ceil(len(values)*fraction)-1)] if values else None


def tiles(bounds,zoom):
    n=2**zoom
    def point(lon,lat):return ((lon+180)/360*n,(1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*n)
    x,y=point((bounds['west']+bounds['east'])/2,(bounds['south']+bounds['north'])/2)
    west,north=point(bounds['west'],bounds['north']);east,south=point(bounds['east'],bounds['south'])
    return [[zoom,tx,ty] for ty in range(int(y)-1,int(y)+2) for tx in range(int(x)-1,int(x)+2) if tx+1>west and tx<east and ty+1>north and ty<south]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--format',choices=['png','webp'],default='png');parser.add_argument('--server',default='http://127.0.0.1:5000');parser.add_argument('--operator',action='store_true');parser.add_argument('--token-stdin',action='store_true');parser.add_argument('--tile-scale',type=int,choices=[1,2],default=1);parser.add_argument('--username');parser.add_argument('--ids',default='2,5');parser.add_argument('--zooms',default='14,17,20');parser.add_argument('--rounds',type=int,default=3);parser.add_argument('--concurrency',type=int,default=6);parser.add_argument('--manifest',type=Path);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if args.format=='webp' and args.tile_scale!=2:parser.error('WebP uses --tile-scale 2')
    server=args.server.rstrip('/');parsed=urlsplit(server)
    if parsed.scheme not in {'http','https'} or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:parser.error('Use an HTTP(S) URL without embedded credentials')
    if args.operator and parsed.hostname not in {'localhost','127.0.0.1','::1'}:parser.error('--operator is restricted to the local app container')
    if not args.operator and not args.token_stdin and not args.username:parser.error('--username is required')
    session=requests.Session()
    if args.token_stdin:session.cookies.set('access_token',sys.stdin.readline().strip())
    elif args.operator:
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
        from database import Database
        from services.auth_service import create_access_token
        with Database().cursor() as c:
            c.execute("SELECT id,username,session_version FROM users WHERE role='admin' AND is_active ORDER BY id LIMIT 1");user=c.fetchone()
        session.cookies.set('access_token',create_access_token({'uid':user['id'],'u':user['username'],'ver':user['session_version']},expires_in=7200))
    else:
        password=os.environ.get('BOTPLUS_PASSWORD') or getpass.getpass('Password: ')
        response=session.post(server+'/api/auth/login',json={'username':args.username,'password':password},timeout=30);response.raise_for_status()
    if args.manifest:cases=json.loads(args.manifest.read_text())['cases']
    else:
        response=session.get(server+'/api/orthophotos',timeout=30);response.raise_for_status();catalog=response.json();ids=[int(i) for i in args.ids.split(',')]
        cases=[{'ortho_id':r['id'],'zoom':z,'tiles':tiles(r['wgs84_bounds'],z)} for r in catalog if r['id'] in ids for z in map(int,args.zooms.split(','))]
    if args.tile_scale==2:
        cases=[{**case,'tiles':[list(t) for t in sorted({(z-1,x//2,y//2) for z,x,y in case['tiles']})]} for case in cases]
    cookies=session.cookies.get_dict();local=threading.local();results=[]
    def fetch(item):
        if not hasattr(local,'session'):
            local.session=requests.Session();local.session.cookies.update(cookies)
        identifier,tile=item;z,x,y=tile;started=time.perf_counter()
        try:
            r=local.session.get(f'{server}/api/orthophotos/{identifier}/tiles/{z}/{x}/{y}{'@2x' if args.tile_scale==2 else ''}.{args.format}',timeout=60)
            return {'tile':tile,'seconds':time.perf_counter()-started,'status':r.status_code,'png':(r.content.startswith(b'\x89PNG\r\n\x1a\n') if args.format=='png' else r.content[:4]==b'RIFF' and r.content[8:12]==b'WEBP'),'bytes':len(r.content),'sha256':hashlib.sha256(r.content).hexdigest(),'cache':r.headers.get('X-Raster-Cache'),'server_timing':r.headers.get('Server-Timing')}
        except requests.RequestException as e:return {'tile':tile,'seconds':time.perf_counter()-started,'status':0,'png':False,'error':type(e).__name__}
    for case in cases:
        for iteration in range(args.rounds):
            started=time.perf_counter();first=None;rows=[]
            with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
                for future in concurrent.futures.as_completed([pool.submit(fetch,(case['ortho_id'],t)) for t in case['tiles']]):
                    value=future.result();rows.append(value)
                    if first is None and value['status']==200 and value['png']:first=time.perf_counter()-started
            summary={'ortho_id':case['ortho_id'],'zoom':case['zoom'],'round':iteration+1,'tiles':len(rows),'ok':sum(r['status']==200 and r['png'] for r in rows),'first_seconds':first,'all_seconds':time.perf_counter()-started,'p50_seconds':statistics.median(r['seconds'] for r in rows) if rows else None,'p95_seconds':percentile([r['seconds'] for r in rows],.95),'responses':rows}
            results.append(summary);print(json.dumps({k:v for k,v in summary.items() if k!='responses'}),flush=True)
    report={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'concurrency':args.concurrency,'rounds':args.rounds,'tile_scale':args.tile_scale,'format':args.format,'cases':cases,'results':results,'note':'Live system; OS/NAS caches not flushed. First pass is not guaranteed physically cold.'}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
