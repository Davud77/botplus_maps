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
    def register(self,key):return self.editor.post('/api/imports/register',json={'root_id':'local','key':key})
    def test_original_registered_without_job_or_cog_generation(self):
        before=self.original.read_bytes();response=self.register('plain.tif');self.assertEqual(response.status_code,201,response.json)
        identifier=response.json['result']['ortho_id']
        self.assertEqual(self.original.read_bytes(),before);self.assertFalse((self.folder/'products').exists())
        with self.db.cursor() as c:
            c.execute('SELECT count(*) AS n FROM import_jobs');self.assertEqual(c.fetchone()['n'],0)
            c.execute('SELECT crs,is_cog FROM orthophotos WHERE id=%s',(identifier,));row=c.fetchone();self.assertEqual(row['crs'],'EPSG:4326');self.assertFalse(row['is_cog'])
        again=self.register('plain.tif');self.assertTrue(again.json['result']['existing']);self.assertEqual(again.json['result']['ortho_id'],identifier)
    def test_missing_crs_creates_stable_unknown_name_without_guessing(self):
        ds=self.gdal.GetDriverByName('GTiff').Create(str(self.folder/'sources'/'no-crs.tif'),8,8,1,self.gdal.GDT_Byte);ds.GetRasterBand(1).Fill(1);ds=None
        r=self.register('no-crs.tif');self.assertEqual(r.status_code,201,r.json);name=r.json['result']['projection'];self.assertTrue(name.startswith('unknown_'))
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
