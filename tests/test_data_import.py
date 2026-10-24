import json
import os
import unittest
from unittest.mock import patch
import test_import_jobs as existing
import test_workspace_integration as workspace
from controllers import data_import


@unittest.skipUnless(os.environ.get('TEST_POSTGIS')=='1','Requires disposable PostGIS/GDAL')
class DirectImportTests(unittest.TestCase):
    cleanup_schema=workspace.WorkspaceIntegrationTests.cleanup_schema
    client=workspace.WorkspaceIntegrationTests.client
    def setUp(self):
        existing.ImportIntegrationTests.setUp(self)
        p=patch.object(data_import,'Database',return_value=self.db);p.start();self.addCleanup(p.stop)
        self.app.register_blueprint(data_import.data_import_blueprint,url_prefix='/api')
        import config
        for key,value in [('MEDIA_ROOT',str(self.folder/'media')),('TEMP_FOLDER',str(self.folder/'temp'))]:
            patcher=patch.object(config,key,value);patcher.start();self.addCleanup(patcher.stop)
    def register(self,key):
        response=self.editor.post('/api/imports/register',json={'root_id':'local','key':key})
        self.assertEqual(response.status_code,202,response.json)
        import import_jobs,job_worker
        result=job_worker.execute(import_jobs.claim_next(self.db),self.db)
        self.assertIsNotNone(result)
        # Return the finished result while checking that HTTP itself only enqueues.
        return type('Finished',(),{'json':{'result':result},'status_code':202})()
    def test_original_queued_copied_and_registered_without_cog_generation(self):
        before=self.original.read_bytes();response=self.register('plain.tif');self.assertEqual(response.status_code,202,response.json)
        identifier=response.json['result']['ortho_id']
        self.assertEqual(self.original.read_bytes(),before);self.assertFalse((self.folder/'products').exists())
        with self.db.cursor() as c:
            c.execute('SELECT count(*) AS n FROM import_jobs');self.assertEqual(c.fetchone()['n'],1)
            c.execute('SELECT crs,is_cog FROM orthophotos WHERE id=%s',(identifier,));row=c.fetchone();self.assertEqual(row['crs'],'EPSG:4326');self.assertFalse(row['is_cog'])
        again=self.register('plain.tif');self.assertTrue(again.json['result']['existing']);self.assertEqual(again.json['result']['ortho_id'],identifier)
    def test_missing_crs_creates_stable_unknown_name_without_guessing(self):
        ds=self.gdal.GetDriverByName('GTiff').Create(str(self.folder/'sources'/'no-crs.tif'),8,8,1,self.gdal.GDT_Byte);ds.GetRasterBand(1).Fill(1);ds=None
        r=self.register('no-crs.tif');self.assertEqual(r.status_code,202,r.json);name=r.json['result']['projection'];self.assertTrue(name.startswith('unknown_'))
        with self.db.cursor() as c:
            c.execute('SELECT name,definition,resolved FROM coordinate_systems WHERE id=%s',(name,));p=c.fetchone();self.assertEqual(p['name'],name);self.assertEqual(p['definition'],'');self.assertFalse(p['resolved'])
            c.execute('SELECT geometry,crs FROM orthophotos WHERE id=%s',(r.json['result']['ortho_id'],));o=c.fetchone();self.assertIsNone(o['geometry']);self.assertEqual(o['crs'],name)
        self.assertEqual(self.viewer.post('/api/imports/register',json={'root_id':'local','key':'plain.tif'}).status_code,403)
    def test_browse_only_allowed_root_and_returns_entries_without_data(self):
        r=self.editor.get('/api/imports/browse',query_string={'root_id':'local','key':'.'});self.assertEqual(r.status_code,200)
        self.assertIn('plain.tif',[x['name'] for x in r.json['entries']]);self.assertIsNone(r.json['parent'])
        self.assertEqual(self.editor.get('/api/imports/browse?root_id=local&key=../').status_code,400)
    def test_processing_is_explicit_and_logs_admin_only(self):
        r=self.register('plain.tif');identifier=r.json['result']['ortho_id']
        response=self.editor.post(f'/api/imports/rasters/{identifier}/prepare');self.assertEqual(response.status_code,202,response.json)
        self.assertEqual(self.editor.get('/api/system/logs').status_code,403)
        self.assertEqual(self.admin.get('/api/system/logs').status_code,200)

    def test_imported_raster_reprojection_and_preview_run_as_queue_jobs(self):
        import config,import_jobs,job_worker
        identifier=self.register('plain.tif').json['result']['ortho_id']
        with patch.object(config,'MEDIA_ROOT',str(self.folder/'media')),patch.object(config,'TEMP_FOLDER',str(self.folder/'temp')):
            for operation in ('reproject','preview'):
                job=import_jobs.enqueue_operation(self.ids['editor'],operation,operation,{'ortho_id':identifier},self.db)
                self.assertEqual(job['status'],'queued')
                self.assertIsNotNone(job_worker.execute(import_jobs.claim_next(self.db),self.db))
                with self.db.cursor() as c:
                    c.execute('SELECT status,progress FROM import_jobs WHERE id=%s',(str(job['id']),))
                    row=c.fetchone();self.assertEqual(row['status'],'succeeded');self.assertEqual(row['progress'],100)
            with self.db.cursor() as c:
                c.execute('SELECT crs FROM orthophotos WHERE id<>%s',(identifier,))
                self.assertEqual(c.fetchone()['crs'],'EPSG:3857')
        self.assertTrue(self.original.exists())

    def test_nas_folder_is_one_background_task_and_copies_all_geotiffs(self):
        import import_jobs,job_worker
        response=self.editor.post('/api/imports/register',json={'root_id':'local','key':'.'})
        self.assertEqual(response.status_code,202,response.json)
        with self.db.cursor() as cur:
            cur.execute('SELECT count(*) AS n FROM orthophotos');self.assertEqual(cur.fetchone()['n'],0)
        result=job_worker.execute(import_jobs.claim_next(self.db),self.db)
        self.assertEqual(result,{'processed':2,'imported':2,'failed':0})
        with self.db.cursor() as cur:
            cur.execute('SELECT asset FROM raster_sources');assets=cur.fetchall()
            self.assertEqual(len(assets),2)
            for row in assets:
                path=import_jobs.asset_path(row['asset'])
                self.assertTrue(path.is_relative_to(import_jobs.staging_root()))
        self.assertTrue(self.original.exists());self.assertTrue(self.cog.exists())

    def test_new_upload_has_automatic_preview(self):
        import import_jobs,job_worker,config
        from io import BytesIO
        response=self.editor.post('/api/imports/files',data={'file':(BytesIO(self.original.read_bytes()),'automatic.tif')},content_type='multipart/form-data')
        self.assertEqual(response.status_code,202)
        result=job_worker.execute(import_jobs.claim_next(self.db),self.db)
        self.assertIsNotNone(result)
        with self.db.cursor() as cur:
            cur.execute('SELECT preview_filename FROM orthophotos WHERE id=%s',(result['ortho_id'],));name=cur.fetchone()['preview_filename']
        self.assertTrue(name)
        from pathlib import Path
        from PIL import Image
        with Image.open(Path(config.MEDIA_ROOT)/'orthophotos'/name) as preview:
            self.assertLessEqual(max(preview.size),400)
            self.assertEqual(preview.format,'PNG')

    def test_custom_projection_is_registered_reused_and_renames_every_ortho(self):
        from osgeo import osr
        from services.ortho_service import OrthoService
        from managers.ortho_manager import OrthoManager
        srs=osr.SpatialReference();srs.ImportFromEPSG(32640)
        first=self.folder/'sources'/'custom.tif'
        dataset=self.gdal.GetDriverByName('GTiff').Create(str(first),16,16,1,self.gdal.GDT_Byte)
        dataset.SetGeoTransform([500000,1,0,4800000,0,-1]);dataset.SetProjection(srs.ExportToWkt());dataset.GetRasterBand(1).Fill(100);dataset=None
        original=self.register('custom.tif').json['result']['ortho_id']
        import shutil
        shutil.copyfile(first,self.folder/'sources'/'custom-two.tif')
        second=self.register('custom-two.tif').json['result']['ortho_id']
        with self.db.cursor() as cur:
            cur.execute('SELECT crs FROM orthophotos WHERE id=ANY(%s)',([original,second],));ids=[r['crs'] for r in cur.fetchall()]
            self.assertEqual(ids[0],ids[1]);projection_id=ids[0]
            cur.execute('SELECT name FROM coordinate_systems WHERE id=%s',(projection_id,));self.assertIsNotNone(cur.fetchone())
        response=self.admin.patch('/api/settings/coordinate-systems/'+projection_id,json={'name':'Местная система координат'})
        self.assertEqual(response.status_code,200,response.json)
        service=OrthoService.__new__(OrthoService);service.db=self.db;service.manager=OrthoManager(self.db,ensure_schema=False)
        rows=[row for row in service.get_all() if row['id'] in [original,second]]
        self.assertEqual(len(rows),2)
        self.assertTrue(all(r['crs']==projection_id and r['crs_name']=='Местная система координат' for r in rows))
        self.assertEqual(self.editor.patch('/api/settings/coordinate-systems/'+projection_id,json={'name':'Нет'}).status_code,403)

    def test_projection_without_definition_can_be_renamed_without_guessing_crs(self):
        ds=self.gdal.GetDriverByName('GTiff').Create(str(self.folder/'sources'/'unnamed.tif'),8,8,1,self.gdal.GDT_Byte);ds=None
        identifier=self.register('unnamed.tif').json['result']['ortho_id']
        with self.db.cursor() as cur:
            cur.execute('SELECT crs FROM orthophotos WHERE id=%s',(identifier,));code=cur.fetchone()['crs']
        response=self.admin.patch('/api/settings/coordinate-systems/'+code,json={'name':'Ожидает привязки'})
        self.assertEqual(response.status_code,200,response.json)
        row=response.json['coordinate_system'];self.assertEqual(row['id'],code);self.assertEqual(row['definition'],'');self.assertFalse(row['resolved'])

    def test_rename_preserves_source_and_selected_projection_runs_in_background(self):
        import import_jobs,job_worker
        from controllers.ortho_controller import OrthoController
        from managers.ortho_manager import OrthoManager
        from services.ortho_service import OrthoService
        controller=OrthoController.__new__(OrthoController)
        controller.db=self.db;controller.ortho_manager=OrthoManager(self.db,ensure_schema=False)
        controller.ortho_service=OrthoService(self.db,controller.ortho_manager,None,None,None)
        self.app.add_url_rule('/api/ortho-edit/<int:ortho_id>',view_func=controller.update_ortho,methods=['PUT'])
        self.app.add_url_rule('/api/ortho-edit/<int:ortho_id>/reproject',view_func=controller.reproject_ortho,methods=['POST'])
        identifier=self.register('plain.tif').json['result']['ortho_id']
        before=self.original.read_bytes()
        response=self.editor.put(f'/api/ortho-edit/{identifier}',json={'display_name':'  План участка  '})
        self.assertEqual(response.status_code,200,response.json)
        ortho=controller.ortho_manager.get_ortho_by_id(identifier)
        self.assertEqual(ortho.display_name,'План участка');self.assertEqual(ortho.filename,'plain.tif')
        self.assertEqual(controller.ortho_service.get_all()[0]['display_name'],'План участка')
        self.assertEqual(self.editor.put(f'/api/ortho-edit/{identifier}',json={'display_name':'  '}).status_code,400)
        self.assertEqual(self.editor.put('/api/ortho-edit/999999',json={'display_name':'missing'}).status_code,404)
        with patch('services.map_settings.Database',return_value=self.db):
            response=self.editor.post(f'/api/ortho-edit/{identifier}/reproject',json={'target_crs':'EPSG:32639'})
            self.assertEqual(response.status_code,202,response.json)
            self.assertEqual(self.editor.post(f'/api/ortho-edit/{identifier}/reproject',json={'target_crs':'missing'}).status_code,400)
        job=import_jobs.claim_next(self.db)
        self.assertEqual(job['source']['payload']['target_crs'],'EPSG:32639')
        self.assertIsNotNone(job_worker.execute(job,self.db))
        with self.db.cursor() as cur:
            cur.execute('SELECT crs FROM orthophotos WHERE id<>%s',(identifier,))
            self.assertEqual(cur.fetchone()['crs'],'EPSG:32639')
        self.assertEqual(self.original.read_bytes(),before)
