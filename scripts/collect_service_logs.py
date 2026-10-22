"""Export a bounded, redacted Docker log snapshot. API never gets the Docker socket."""
import argparse
import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile


def redact(text):
    text=re.sub(r'(postgres(?:ql)?://[^:\s]+:)[^@\s]+@',r'\1[redacted]@',text,flags=re.I)
    text=re.sub(r'(?i)((?:password|passwd|secret|token|authorization|rootpass)\s*[:=]\s*)[^\s,;]+',r'\1[redacted]',text)
    text=re.sub(r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+','[redacted JWT]',text)
    return text[:2000]


def main():
    p=argparse.ArgumentParser();p.add_argument('--project',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--uid',type=int,default=10001);p.add_argument('--gid',type=int,default=10001);args=p.parse_args()
    result=subprocess.run(['docker','ps','--filter','label=com.docker.compose.project='+args.project,'--format','{{.ID}}\t{{.Label "com.docker.compose.service"}}'],capture_output=True,text=True,timeout=10,check=True)
    entries=[];now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    for row in result.stdout.splitlines():
        identifier,service=row.split('\t',1)
        if service not in {'app','worker','media-worker','db','titiler','pgbouncer'}:continue
        try:
            logs=subprocess.run(['docker','logs','--tail','150','--since','30m','--timestamps',identifier],capture_output=True,text=True,timeout=8)
            for line in (logs.stdout+'\n'+logs.stderr).splitlines():
                at,sep,message=line.partition(' ')
                entries.append({'at':at if sep and at[:4].isdigit() else now,'service':service,'message':redact(message if sep else line)})
        except subprocess.TimeoutExpired:entries.append({'at':now,'service':service,'message':'Log collection timed out'})
    # Read Docker as the operator; write into app-owned/NAS paths only AFTER
    # dropping privileges, so an app-writable symlink cannot cause a root write.
    if os.geteuid()==0:
        os.setgroups([]);os.setgid(args.gid);os.setuid(args.uid)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    value=json.dumps({'collected_at':now,'entries':entries[-1000:]},ensure_ascii=False)
    with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=args.output.parent,delete=False) as stream:
        temporary=Path(stream.name);stream.write(value);stream.flush();os.fsync(stream.fileno())
    os.replace(temporary,args.output)
    print('Service log snapshot updated')


if __name__=='__main__':main()
