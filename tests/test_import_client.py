import argparse
from contextlib import redirect_stdout
from io import StringIO,BytesIO
import json
import os
import unittest
from unittest.mock import patch
from server import import_client


class ClientTests(unittest.TestCase):
    def test_import_sends_only_source_reference_not_raster_bytes(self):
        requests=[]
        class Opener:
            def open(self,request,timeout):
                requests.append(request)
                return BytesIO(json.dumps({'status':'ok'} if request.full_url.endswith('/auth/login') else {'job':{'id':'job','status':'queued'}}).encode())
        args=argparse.Namespace(server='http://localhost:5580',username='operator',command='import-raster',root='nas',path='does-not-exist-on-this-client/huge.tif',title='',source_crs_id=None,idempotency_key='same-source',wait=False)
        output=StringIO()
        with patch.dict(os.environ,{'BOTPLUS_PASSWORD':'test-only-password'}),patch.object(import_client,'build_opener',return_value=Opener()),redirect_stdout(output):
            self.assertEqual(import_client.run(args),0)
        self.assertEqual(len(requests),2)
        payload=json.loads(requests[1].data)
        self.assertEqual(payload['root_id'],'nas')
        self.assertEqual(payload['key'],args.path)
        self.assertNotIn('test-only-password',output.getvalue())
        self.assertEqual(requests[1].get_header('Content-type'),'application/json')

    def test_invalid_server_urls_are_rejected_before_login(self):
        for server in ['file:///etc/passwd','https://user:password@host','http://host/?token=secret']:
            with self.subTest(server=server),self.assertRaises(ValueError):import_client.run(argparse.Namespace(server=server))
