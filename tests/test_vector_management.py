import os
import unittest
from uuid import uuid4
from psycopg2 import sql,extensions
import test_workspace_integration as workspace
from controllers import vector

@unittest.skipUnless(os.environ.get('TEST_POSTGIS')=='1','requires isolated PostGIS')
class VectorManagementTests(unittest.TestCase):
    setUp_base=workspace.WorkspaceIntegrationTests.setUp
    cleanup_schema=workspace.WorkspaceIntegrationTests.cleanup_schema
    client=workspace.WorkspaceIntegrationTests.client
    def setUp(self):
        self.setUp_base()
        self.app.register_blueprint(vector.vector_bp,url_prefix='/api')
        self.dbname=extensions.parse_dsn(self.dsn)['dbname']
        self.custom='management_'+uuid4().hex
        def cleanup():
            with self.db.cursor(write=True) as cur:cur.execute(sql.SQL('DROP SCHEMA IF EXISTS {} CASCADE').format(sql.Identifier(self.custom)))
        self.addCleanup(cleanup)
    def test_schema_creation_listing_and_restricted_deletion(self):
        path='/api/vector/schemas/'+self.dbname
        self.assertEqual(self.viewer.post(path,json={'name':self.custom}).status_code,403)
        response=self.editor.post(path,json={'name':self.custom});self.assertEqual(response.status_code,201,response.json)
        self.assertIn(self.custom,[s['name'] for s in self.editor.get(path).json['schemas']])
        response=self.editor.post('/api/vector/layers/create',json={'dbName':self.dbname,'schema':self.custom,'tableName':'points','geomType':'POINT'})
        self.assertEqual(response.status_code,200,response.json)
        self.assertEqual(self.admin.delete(path+'/'+self.custom).status_code,409)
        layer=f'/api/vector/layers/{self.dbname}/{self.custom}/points'
        self.assertEqual(self.editor.delete(layer).status_code,403)
        self.assertEqual(self.admin.delete(layer).status_code,200)
        self.assertEqual(self.admin.delete(path+'/'+self.custom).status_code,200)
    def test_system_data_and_invalid_names_are_protected(self):
        path='/api/vector/schemas/'+self.dbname
        self.assertEqual(self.admin.delete(path+'/public').status_code,403)
        self.assertEqual(self.admin.delete(f'/api/vector/layers/{self.dbname}/public/photos_4326').status_code,403)
        self.assertEqual(self.admin.delete('/api/vector/databases/'+self.dbname).status_code,403)
        for body in ([],{'name':'public'},{'name':'bad;drop schema public'}):
            self.assertEqual(self.admin.post(path,json=body).status_code,400)
    def test_create_inspect_and_delete_custom_database(self):
        name='management'+uuid4().hex
        response=self.admin.post('/api/vector/create_db',json={'name':name});self.assertEqual(response.status_code,200,response.json)
        self.addCleanup(lambda:self.admin.delete('/api/vector/databases/'+name))
        self.assertEqual(self.admin.get('/api/vector/schemas/'+name).status_code,200)
        self.assertEqual(self.admin.delete('/api/vector/databases/'+name).status_code,200)
