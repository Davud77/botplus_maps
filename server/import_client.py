"""Small stdlib HTTP client; never reads or uploads a local raster."""
import getpass
from http.cookiejar import CookieJar
import json
import os
import time
from urllib.error import HTTPError
from urllib.request import build_opener,HTTPCookieProcessor,Request
from urllib.parse import urlsplit


def run(args):
    server=args.server.rstrip('/')
    url=urlsplit(server)
    if url.scheme not in {'http','https'} or not url.netloc or url.username or url.password or url.query or url.fragment:
        raise ValueError('Use an HTTP(S) server URL without embedded credentials')
    opener=build_opener(HTTPCookieProcessor(CookieJar()))
    def request(path,method='GET',body=None):
        req=Request(server+'/api'+path,method=method,data=json.dumps(body).encode() if body is not None else None,
                    headers={'Content-Type':'application/json'})
        try:
            with opener.open(req,timeout=60) as response: return json.load(response)
        except HTTPError as exc:
            try: message=json.load(exc).get('message') or str(exc.code)
            except (ValueError,AttributeError): message=str(exc.code)
            raise ValueError(message) from exc
    try: password=os.environ.get('BOTPLUS_PASSWORD') or getpass.getpass('BotPlus password: ')
    except EOFError as exc: raise ValueError('Use an interactive terminal or provide BOTPLUS_PASSWORD in the environment.') from exc
    request('/auth/login','POST',{'username':args.username,'password':password})
    if args.command=='map-prepare':
        if not 1<=len(args.ids)<=100:raise ValueError('Select 1 to 100 raster IDs')
        rows=[request(f'/raster-display/orthophotos/{identifier}','POST',{'max_zoom':args.max_zoom})['job'] for identifier in args.ids]
        if args.wait:
            while any(row['status'] in {'queued','running'} for row in rows):
                time.sleep(2);rows=[request('/raster-display/jobs/'+row['id'])['job'] for row in rows]
        result={'jobs':rows}
    elif args.command=='map-jobs':result=request('/raster-display/jobs')
    elif args.command=='map-job':result=request('/raster-display/jobs/'+args.id+('/'+args.action if args.action else ''),'POST' if args.action else 'GET',{} if args.action else None)
    elif args.command=='import-raster':
        if not getattr(args,'prepare',False):
            if args.source_crs_id or args.wait:raise ValueError('--source-crs-id and --wait require explicit --prepare')
            result=request('/imports/register','POST',{'root_id':args.root,'key':args.path,'title':args.title})
            print(json.dumps(result,ensure_ascii=False,indent=2));return 0
        result=request('/imports/jobs','POST',{'root_id':args.root,'key':args.path,'title':args.title,'source_crs_id':args.source_crs_id,'idempotency_key':args.idempotency_key})
        if args.wait:
            job_id=result['job']['id']
            while result['job']['status'] in {'queued','running'}:
                time.sleep(2)
                result=request('/imports/jobs/'+job_id)
    elif args.command=='jobs': result=request('/imports/jobs')
    elif args.command=='job':
        result=request('/imports/jobs/'+args.id+('/'+args.action if args.action else ''),'POST' if args.action else 'GET',{} if args.action else None)
    else: result=request('/imports/sources')
    print(json.dumps(result,ensure_ascii=False,indent=2,default=str))
    return 2 if (isinstance(result.get('job'),dict) and result['job']['status'] in {'failed','cancelled'}) or (args.command=='map-prepare' and any(row['status'] in {'failed','cancelled'} for row in result.get('jobs',[]))) else 0
