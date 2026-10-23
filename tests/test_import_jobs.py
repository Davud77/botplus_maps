"""Native GDAL + isolated PostGIS checks for durable, non-destructive imports."""
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_workspace_integration as workspace_tests
import import_jobs as jobs
import job_worker
from controllers import import_controller, data_import
from managers.ortho_manager import OrthoManager


@unittest.skipUnless(os.environ.get('TEST_POSTGIS')=='1','requires isolated PostGIS database')
class ImportIntegrationTests(unittest.TestCase):
    cleanup_schema=workspace_tests.WorkspaceIntegrationTests.cleanup_schema
    client=workspace_tests.WorkspaceIntegrationTests.client

    def setUp(self):
        workspace_tests.WorkspaceIntegrationTests.setUp(self)
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name)
        env={'LOCAL_SOURCE_ROOTS':json.dumps({'local':str(self.folder/'sources')}),
             'IMPORT_PRODUCTS_DIR':str(self.folder/'products'),'IMPORT_STAGING_DIR':str(self.folder/'staging'),'RASTER_TILE_CACHE_DIR':str(self.folder/'tile-cache')}
        (self.folder/'sources').mkdir()
        patcher=patch.dict(os.environ,env);patcher.start();self.addCleanup(patcher.stop)
        for module in [jobs,import_controller,data_import]:
            patcher=patch.object(module,'Database',return_value=self.db);patcher.start();self.addCleanup(patcher.stop)
        with self.db.cursor(write=True) as cur: cur.execute('DROP TABLE orthophotos')
        OrthoManager(self.db)
        self.app.register_blueprint(import_controller.imports_blueprint,url_prefix='/api')
        from osgeo import gdal,osr
        self.gdal=gdal
        self.original=self.folder/'sources'/'plain.tif'
        ds=gdal.GetDriverByName('GTiff').Create(str(self.original),64,64,1,gdal.GDT_Byte)
        ds.SetGeoTransform([47,0.0001,0,43,0,-0.0001]);srs=osr.SpatialReference();srs.ImportFromEPSG(4326);ds.SetProjection(srs.ExportToWkt());ds.GetRasterBand(1).Fill(128);ds=None
        self.cog=self.folder/'sources'/'ready.tif'
        ds=gdal.Translate(str(self.cog),str(self.original),format='COG');ds=None
        job_worker.STOP.clear()

    def enqueue(self,path='ready.tif',client=None,**kwargs):
        response=(client or self.editor).post('/api/imports/jobs',json={'root_id':'local','key':path,**kwargs})
        self.assertEqual(response.status_code,202,response.get_data(as_text=True))
        return response.get_json()['job']

    def test_role_ownership_path_and_idempotency_boundaries(self):
        self.assertEqual(self.viewer.get('/api/imports/sources').status_code,403)
        self.assertEqual(self.viewer.post('/api/imports/jobs',json={}).status_code,403)
        sources=self.editor.get('/api/imports/sources').get_json()
        self.assertEqual(sources['sources'],[{'id':'local','name':'local'}])
        self.assertNotIn(str(self.folder),json.dumps(sources))
        job=self.enqueue(idempotency_key='one')
        self.assertEqual(self.enqueue(idempotency_key='one')['id'],job['id'])
        self.assertEqual(self.other.get('/api/imports/jobs/'+job['id']).status_code,404)
        self.assertEqual(self.admin.get('/api/imports/jobs/'+job['id']).status_code,200)
        (self.folder/'sources'/'escape.tif').symlink_to(self.folder/'outside.tif')
        (self.folder/'outside.tif').write_bytes(b'outside')
        for path in ['../outside.tif','escape.tif',str(self.cog),'missing.tif','ready.txt']:
            self.assertEqual(self.editor.post('/api/imports/jobs',json={'root_id':'local','key':path}).status_code,400)
        self.assertEqual(self.editor.post('/api/imports/jobs',json={'root_id':'__uploads','key':'anything.tif'}).status_code,400)
        self.assertEqual(self.editor.post('/api/imports/jobs',json={'root_id':'local','key':'plain.tif','idempotency_key':'one'}).status_code,400)

    def test_ready_cog_is_registered_without_copy_and_duplicate_result(self):
        before=self.cog.read_bytes();stat=jobs.fingerprint(self.cog)
        job=self.enqueue();claimed=jobs.claim(self.db);result=job_worker.execute(claimed,self.db)
        self.assertTrue(result['no_copy']);self.assertEqual(self.cog.read_bytes(),before)
        self.assertEqual(jobs.fingerprint(self.cog),stat)
        asset=jobs.asset_record(result['ortho_id'],self.db)
        self.assertEqual(jobs.asset_path(asset),self.cog)
        self.assertFalse(jobs.products_root().exists())
        second=self.enqueue(client=self.other)
        other_result=job_worker.execute(jobs.claim(self.db),self.db)
        self.assertEqual(other_result['ortho_id'],result['ortho_id'])
        self.assertEqual(self.editor.get('/api/imports/jobs/'+job['id']).get_json()['job']['status'],'succeeded')
        with self.db.cursor() as cur:
            cur.execute('SELECT count(*) AS n FROM orthophotos');self.assertEqual(cur.fetchone()['n'],1)

    def test_plain_geotiff_creates_cog_preserving_original_and_detects_changes(self):
        before=self.original.read_bytes();self.enqueue('plain.tif')
        result=job_worker.execute(jobs.claim(self.db),self.db)
        self.assertIsNotNone(result);self.assertFalse(result['no_copy'])
        self.assertEqual(self.original.read_bytes(),before)
        asset=jobs.asset_record(result['ortho_id'],self.db);product=jobs.asset_path(asset)
        self.assertNotEqual(product,self.original)
        ds=self.gdal.Open(str(product));self.assertEqual(ds.GetMetadata('IMAGE_STRUCTURE')['LAYOUT'],'COG');ds=None
        self.original.write_bytes(before+b'changed')
        with self.assertRaisesRegex(ValueError,'изменён'):jobs.asset_path(asset)

    def test_cancel_retry_and_changed_source_do_not_publish(self):
        job=self.enqueue()
        self.assertEqual(self.editor.post('/api/imports/jobs/'+job['id']+'/cancel',json={}).status_code,200)
        self.assertIsNone(jobs.claim(self.db))
        self.assertEqual(self.editor.post('/api/imports/jobs/'+job['id']+'/retry',json={}).status_code,200)
        claimed=jobs.claim(self.db)
        self.assertEqual(self.editor.post('/api/imports/jobs/'+job['id']+'/cancel',json={}).status_code,200)
        self.assertIsNone(job_worker.execute(claimed,self.db))
        self.assertEqual(self.editor.get('/api/imports/jobs/'+job['id']).get_json()['job']['status'],'cancelled')
        self.assertTrue(self.cog.is_file())
        self.editor.post('/api/imports/jobs/'+job['id']+'/retry',json={})
        claimed=jobs.claim(self.db);self.cog.write_bytes(self.cog.read_bytes()+b'changed')
        self.assertIsNone(job_worker.execute(claimed,self.db))
        with self.db.cursor() as cur:
            cur.execute('SELECT count(*) AS n FROM orthophotos');self.assertEqual(cur.fetchone()['n'],0)

    def test_expired_lease_is_reclaimed_and_old_worker_cannot_publish(self):
        job=self.enqueue();old=jobs.claim(self.db)
        with self.db.cursor(write=True) as cur:cur.execute("UPDATE import_jobs SET lease_until=NOW()-INTERVAL '1 second' WHERE id=%s",(job['id'],))
        current=jobs.claim(self.db)
        self.assertEqual(current['attempts'],2);self.assertNotEqual(old['lease_token'],current['lease_token'])
        self.assertIsNone(job_worker.execute(old,self.db))
        result=job_worker.execute(current,self.db);self.assertIsNotNone(result)
        with self.db.cursor() as cur:
            cur.execute('SELECT count(*) AS n FROM orthophotos');self.assertEqual(cur.fetchone()['n'],1)

    def test_parallel_claims_and_graceful_stop(self):
        self.enqueue();self.enqueue('plain.tif')
        with ThreadPoolExecutor(max_workers=2) as pool:claims=list(pool.map(lambda _:jobs.claim(self.db),range(2)))
        self.assertEqual(len({str(job['id']) for job in claims}),2)
        job_worker.STOP.set()
        try:self.assertIsNone(job_worker.execute(claims[0],self.db))
        finally:job_worker.STOP.clear()
        with self.db.cursor() as cur:
            cur.execute('SELECT status,attempts FROM import_jobs WHERE id=%s',(str(claims[0]['id']),));row=cur.fetchone()
            self.assertEqual(row['status'],'queued');self.assertEqual(row['attempts'],0)

    def test_web_upload_registers_without_processing_and_rejects_invalid_data(self):
        response=self.editor.post('/api/imports/uploads',data={'file':(BytesIO(self.cog.read_bytes()),'uploaded.tif')},content_type='multipart/form-data')
        self.assertEqual(response.status_code,201,response.get_data(as_text=True))
        self.assertIn('ortho_id',response.json['result']);self.assertIsNone(jobs.claim(self.db))
        response=self.editor.post('/api/imports/uploads',data={'file':(BytesIO(b'not a raster'),'fake.tif')},content_type='multipart/form-data')
        self.assertEqual(response.status_code,400);self.assertIsNone(jobs.claim(self.db))
        self.assertEqual(self.editor.post('/api/imports/uploads',data={'file':(BytesIO(b'x'),'bad.zip')}).status_code,400)

    def test_unregister_keeps_source_and_allows_fresh_registration(self):
        from controllers.ortho_controller import OrthoController
        controller=object.__new__(OrthoController);controller.db=self.db;controller.ortho_manager=OrthoManager(self.db,ensure_schema=False)
        self.app.add_url_rule('/api/unregister/<int:ortho_id>',view_func=controller.delete_ortho,methods=['DELETE'])
        self.enqueue();result=job_worker.execute(jobs.claim(self.db),self.db)
        self.assertEqual(self.editor.delete('/api/unregister/'+str(result['ortho_id'])).status_code,200)
        self.assertTrue(self.cog.is_file());self.assertIsNone(jobs.asset_record(result['ortho_id'],self.db))
        fresh=self.enqueue();self.assertEqual(fresh['status'],'queued')
        self.assertIsNotNone(job_worker.execute(jobs.claim(self.db),self.db))

    def test_legacy_web_uploader_registers_original_without_processing(self):
        from controllers.ortho_controller import OrthoController
        controller=object.__new__(OrthoController);controller.db=self.db
        self.app.add_url_rule('/api/upload_ortho',view_func=controller.upload_ortho,methods=['POST'])
        response=self.editor.post('/api/upload_ortho',data={'files':(BytesIO(self.cog.read_bytes()),'old-form.tif')},content_type='multipart/form-data')
        self.assertEqual(response.status_code,201,response.get_data(as_text=True))
        self.assertIn('ortho_id',response.json['result']);self.assertIsNone(jobs.claim(self.db))

    def test_tile_gateway_requests_png_for_local_assets_and_rejects_stale_sources(self):
        self.enqueue();result=job_worker.execute(jobs.claim(self.db),self.db)
        from services.ortho_service import OrthoService
        from werkzeug.exceptions import Conflict
        service=object.__new__(OrthoService);service.db=self.db;service.manager=OrthoManager(self.db,ensure_schema=False)
        with patch('services.ortho_service.requests.get') as request:
            request.return_value.status_code=200;request.return_value.content=b'PNG-fixture'
            self.assertEqual(service.proxy_tile(result['ortho_id'],0,0,0),b'PNG-fixture')
            self.assertTrue(request.call_args.args[0].endswith('/0/0/0.png'))
            self.assertEqual(request.call_args.kwargs['params']['url'],str(self.cog))
            self.cog.write_bytes(self.cog.read_bytes()+b'changed')
            request.reset_mock()
            with self.app.test_request_context(),self.assertRaises(Conflict):service.proxy_tile(result['ortho_id'],0,0,0)
            request.assert_not_called()

    def test_scaled_tile_cache_keeps_authentication_and_source_validation(self):
        from controllers.ortho_controller import OrthoController
        from services.ortho_service import OrthoService
        from test_raster_cache import png
        service=object.__new__(OrthoService);service.db=self.db;service.manager=OrthoManager(self.db,ensure_schema=False)
        controller=object.__new__(OrthoController);controller.ortho_service=service
        self.app.add_url_rule('/api/raster/<int:z>/<int:x>/<int:y>',endpoint='scaled_raster_test',view_func=lambda z,x,y:controller.get_ortho_tile(identifier,z,x,y,scale=2))
        self.enqueue();result=job_worker.execute(jobs.claim(self.db),self.db);identifier=result['ortho_id']
        with patch('services.ortho_service.requests.get') as upstream:
            upstream.return_value.status_code=200;upstream.return_value.content=png(2)
            self.assertEqual(self.app.test_client().get('/api/raster/3/2/2').status_code,401)
            first=self.editor.get('/api/raster/3/2/2');self.assertEqual(first.status_code,200);self.assertEqual(first.headers['X-Raster-Cache'],'MISS')
            again=self.editor.get('/api/raster/3/2/2');self.assertEqual(again.data,first.data);self.assertEqual(again.headers['X-Raster-Cache'],'MEMORY');self.assertEqual(upstream.call_count,1)
            self.assertTrue(upstream.call_args.args[0].endswith('/3/2/2@2x.png'))
            self.assertEqual(self.editor.get('/api/raster/3/99/2').status_code,404);self.assertEqual(upstream.call_count,1)
            from requests import ConnectionError
            upstream.side_effect=ConnectionError('renderer offline')
            self.assertEqual(self.editor.get('/api/raster/3/3/2').status_code,502)
            upstream.side_effect=None
            self.assertEqual(self.editor.get('/api/raster/3/3/2').headers['X-Raster-Cache'],'MISS')
            self.cog.write_bytes(self.cog.read_bytes()+b'changed')
            self.assertEqual(self.editor.get('/api/raster/3/2/2').status_code,409);self.assertEqual(upstream.call_count,3)

    def test_webp_reuses_png_cache_preserves_alpha_and_checks_stale_source(self):
        from controllers.ortho_controller import OrthoController
        from services.ortho_service import OrthoService
        from test_raster_cache import png
        from PIL import Image
        service=object.__new__(OrthoService);service.db=self.db;service.manager=OrthoManager(self.db,ensure_schema=False)
        controller=object.__new__(OrthoController);controller.ortho_service=service
        self.app.add_url_rule('/api/webp/tiles/<int:z>/<int:x>/<int:y>',endpoint='webp_test',view_func=lambda z,x,y:controller.get_ortho_tile(identifier,z,x,y,scale=2,image_format='webp'))
        self.enqueue();result=job_worker.execute(jobs.claim(self.db),self.db);identifier=result['ortho_id']
        image=Image.open(BytesIO(png(2)));image.putpixel((0,0),(0,0,0,0));out=BytesIO();image.save(out,format='PNG');original=out.getvalue()
        with patch('services.ortho_service.requests.get') as upstream:
            upstream.return_value.status_code=200;upstream.return_value.content=original
            self.assertEqual(service.proxy_tile(identifier,3,2,2,scale=2),original)
            self.assertEqual(self.app.test_client().get('/api/webp/tiles/3/2/2').status_code,401)
            first=self.editor.get('/api/webp/tiles/3/2/2');self.assertEqual(first.status_code,200)
            self.assertEqual(first.mimetype,'image/webp');self.assertTrue(first.cache_control.private)
            decoded=Image.open(BytesIO(first.data));self.assertEqual(decoded.size,(512,512));self.assertEqual(decoded.getchannel('A').tobytes(),image.getchannel('A').tobytes())
            again=self.editor.get('/api/webp/tiles/3/2/2');self.assertEqual(first.data,again.data);self.assertEqual(again.headers['X-Raster-Cache'],'MEMORY');self.assertEqual(upstream.call_count,1)
            self.cog.write_bytes(self.cog.read_bytes()+b'changed')
            self.assertEqual(self.editor.get('/api/webp/tiles/3/2/2').status_code,409)

    def test_streamed_tiles_validate_auth_bounds_and_source_before_cache(self):
        import base64
        from controllers.ortho_controller import OrthoController
        from services.ortho_service import OrthoService
        from test_raster_cache import png
        from PIL import Image
        from test_raster_codec import npy
        service=object.__new__(OrthoService);service.db=self.db;service.manager=OrthoManager(self.db,ensure_schema=False)
        controller=object.__new__(OrthoController);controller.ortho_service=service
        self.app.add_url_rule('/api/stream/<int:ortho_id>',endpoint='stream_test',view_func=controller.get_ortho_batch)
        self.enqueue();result=job_worker.execute(jobs.claim(self.db),self.db);identifier=result['ortho_id']
        url=f'/api/stream/{identifier}'
        query={'z':3,'tiles':'2,2;3,2;2,2'}
        with patch('services.ortho_service.requests.get') as upstream:
            upstream.return_value.status_code=200;upstream.return_value.content=npy(Image.open(BytesIO(png(2))))
            self.assertEqual(self.app.test_client().get(url,query_string=query).status_code,401)
            for invalid in [{},{'z':25,'tiles':'0,0'},{'z':3,'tiles':'-1,0'},{'z':3,'tiles':'8,0'},{'z':3,'tiles':';'.join(['0,0']*25)}]:
                self.assertEqual(self.editor.get(url,query_string=invalid).status_code,400)
            response=self.editor.get(url,query_string=query,buffered=True)
            self.assertEqual(response.mimetype,'application/x-ndjson');self.assertTrue(response.cache_control.no_store)
            rows=[json.loads(line) for line in response.data.splitlines()]
            self.assertEqual(len(rows),2);self.assertEqual(upstream.call_count,2)
            for row in rows:
                self.assertEqual(Image.open(BytesIO(base64.b64decode(row['data']))).size,(512,512));self.assertEqual(row['cache'],'MISS')
            again=self.editor.get(url,query_string=query,buffered=True);self.assertEqual(upstream.call_count,2)
            self.cog.write_bytes(self.cog.read_bytes()+b'changed')
            stale=self.editor.get(url,query_string=query,buffered=True)
            self.assertTrue(all(json.loads(line).get('error')==409 for line in stale.data.splitlines()));self.assertEqual(upstream.call_count,2)

    def test_custom_source_crs_override_creates_derivative_without_rewriting_original(self):
        response=self.admin.post('/api/settings/coordinate-systems',json={'name':'Local geographic','definition':'+proj=longlat +datum=WGS84 +no_defs'})
        self.assertEqual(response.status_code,201)
        before=self.cog.read_bytes()
        self.enqueue(source_crs_id=response.get_json()['coordinate_system']['id'])
        result=job_worker.execute(jobs.claim(self.db),self.db)
        self.assertIsNotNone(result);self.assertFalse(result['no_copy'])
        self.assertEqual(self.cog.read_bytes(),before)
        self.assertNotEqual(jobs.asset_path(jobs.asset_record(result['ortho_id'],self.db)),self.cog)
