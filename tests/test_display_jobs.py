from pathlib import Path
import os
import unittest
from unittest.mock import patch
import test_import_jobs as import_tests
import import_jobs
import job_worker
import display_jobs
from controllers import display_controller

@unittest.skipUnless(os.environ.get('TEST_POSTGIS')=='1','requires isolated PostGIS')
class DisplayPreparationTests(unittest.TestCase):
    cleanup_schema=import_tests.ImportIntegrationTests.cleanup_schema
    client=import_tests.ImportIntegrationTests.client
    enqueue=import_tests.ImportIntegrationTests.enqueue
    def setUp(self):
        import_tests.ImportIntegrationTests.setUp(self)
        for module in [display_jobs,display_controller]:
            p=patch.object(module,'Database',return_value=self.db);p.start();self.addCleanup(p.stop)
        self.app.register_blueprint(display_controller.display_blueprint,url_prefix='/api')
        self.enqueue();self.identifier=job_worker.execute(import_jobs.claim(self.db),self.db)['ortho_id']
    def start(self,client=None):
        response=(client or self.editor).post(f'/api/raster-display/orthophotos/{self.identifier}',json={})
        self.assertEqual(response.status_code,202,response.get_data(as_text=True));return response.json['job']
    def claim(self):return import_jobs.claim(self.db,table='raster_display_jobs',event_writer=display_jobs.event)
    def test_prepares_independent_map_product_without_changing_source_or_png_descriptor(self):
        before=self.cog.read_bytes();native=import_jobs.asset_record(self.identifier,self.db)
        queued=self.start();self.assertIsNone(import_jobs.claim(self.db))
        self.assertEqual(self.start()['id'],queued['id'])
        result=display_jobs.execute(self.claim(),self.db);self.assertIsNotNone(result)
        asset=import_jobs.asset_record(self.identifier,self.db);path=display_jobs.display_path(asset,20,2)
        self.assertIsNotNone(path);self.assertEqual(import_jobs.asset_path(asset),self.cog)
        self.assertEqual(display_jobs.base_asset(asset),native);self.assertEqual(self.cog.read_bytes(),before)
        image=self.gdal.Open(str(path));self.assertIn('3857',image.GetProjectionRef());self.assertTrue(max(image.RasterXSize,image.RasterYSize)<=512 or image.GetRasterBand(1).GetOverviewCount());image=None
        self.assertIsNone(display_jobs.display_path(asset,22,2))
        original_key=__import__('raster_cache').RasterCache.key(native,10,1,1,1)
        self.assertEqual(original_key,__import__('raster_cache').RasterCache.key(display_jobs.base_asset(asset),10,1,1,1))
        self.assertEqual(self.editor.get('/api/raster-display/jobs/'+queued['id']).json['job']['status'],'succeeded')
        path.unlink();self.assertIsNone(display_jobs.display_path(asset,20,2));self.assertEqual(self.start()['status'],'queued')
    def test_gateway_keeps_native_png_and_uses_derivative_only_for_screen_tiles(self):
        from io import BytesIO
        from PIL import Image
        from test_raster_cache import png
        from test_raster_codec import npy
        from services.ortho_service import OrthoService
        from managers.ortho_manager import OrthoManager
        service=object.__new__(OrthoService);service.db=self.db;service.manager=OrthoManager(self.db,ensure_schema=False)
        image=png(2)
        with patch('services.ortho_service.requests.get') as upstream:
            upstream.return_value.status_code=200;upstream.return_value.content=image
            self.assertEqual(service.proxy_tile(self.identifier,3,2,2,scale=2),image)
            self.start();self.assertIsNotNone(display_jobs.execute(self.claim(),self.db))
            product=display_jobs.display_path(import_jobs.asset_record(self.identifier,self.db),3,2)
            self.assertEqual(service.proxy_tile(self.identifier,3,2,2,scale=2),image);self.assertEqual(upstream.call_count,1)
            upstream.return_value.content=npy(Image.open(BytesIO(image)))
            value=service.proxy_tile(self.identifier,3,2,2,scale=2,image_format='webp')
            self.assertEqual(Image.open(BytesIO(value)).format,'WEBP');self.assertTrue(upstream.call_args.args[0].endswith('@2x.npy'))
            self.assertEqual(upstream.call_args.kwargs['params']['url'],str(product))
            product.unlink()
            self.assertTrue(service.proxy_tile(self.identifier,3,2,2,scale=2,image_format='webp'));self.assertEqual(upstream.call_count,2)

    def test_custom_projection_remains_in_original_while_map_product_is_3857(self):
        from osgeo import osr
        source=self.folder/'sources'/'custom.tif'
        original=self.gdal.GetDriverByName('GTiff').Create(str(source),64,64,3,self.gdal.GDT_Byte)
        original.SetGeoTransform([1000000,.02,0,0,0,-.02]);srs=osr.SpatialReference()
        srs.SetFromUserInput('+proj=tmerc +lat_0=0 +lon_0=46.8916666667 +k=1 +x_0=1000000 +y_0=-5000000 +datum=WGS84 +units=m +no_defs')
        original.SetProjection(srs.ExportToWkt());original=None;before=source.read_bytes()
        self.enqueue(path='custom.tif');self.identifier=job_worker.execute(import_jobs.claim(self.db),self.db)['ortho_id']
        self.start();self.assertIsNotNone(display_jobs.execute(self.claim(),self.db));self.assertEqual(source.read_bytes(),before)
        original=self.gdal.Open(str(source));self.assertIn('46.8916666667',original.GetProjectionRef())

    def test_access_cancel_retry_and_stale_input_are_isolated_from_import_queue(self):
        self.assertEqual(self.viewer.post(f'/api/raster-display/orthophotos/{self.identifier}',json={}).status_code,403)
        job=self.start();url='/api/raster-display/jobs/'+job['id']
        self.assertEqual(self.other.get(url).status_code,404)
        self.assertEqual(self.admin.get(url).status_code,200)
        self.assertEqual(self.editor.post(url+'/cancel',json={}).status_code,200);self.assertIsNone(self.claim())
        self.assertEqual(self.editor.post(url+'/retry',json={}).status_code,200)
        claimed=self.claim();self.cog.write_bytes(self.cog.read_bytes()+b'changed')
        self.assertIsNone(display_jobs.execute(claimed,self.db))
        self.assertEqual(self.editor.get(url).json['job']['status'],'failed');self.assertIsNone(import_jobs.claim(self.db))
    def test_removed_registration_cannot_publish_derivative(self):
        self.start();claimed=self.claim();prepare=display_jobs.prepare_file
        def remove(*args):
            path=prepare(*args)
            with self.db.cursor(write=True) as c:c.execute('DELETE FROM import_assets WHERE ortho_id=%s',(self.identifier,))
            return path
        with patch.object(display_jobs,'prepare_file',side_effect=remove):self.assertIsNone(display_jobs.execute(claimed,self.db))
        self.assertTrue(self.cog.exists());self.assertFalse(list(import_jobs.products_root().rglob('display.tif')))
    def test_expired_worker_cannot_finish_a_new_workers_lease(self):
        self.start();old=self.claim()
        with self.db.cursor(write=True) as c:c.execute("UPDATE raster_display_jobs SET lease_until=NOW()-INTERVAL '1 second' WHERE id=%s",(old['id'],))
        current=self.claim();self.assertNotEqual(old['lease_token'],current['lease_token'])
        self.assertIsNone(display_jobs.execute(old,self.db));self.assertIsNotNone(display_jobs.execute(current,self.db))
