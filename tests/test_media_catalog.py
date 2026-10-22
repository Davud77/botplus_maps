"""Catalog behavior on disposable PostGIS, including reversible bulk changes."""
import os
import unittest
from unittest.mock import patch
from uuid import uuid4
from flask import Flask
from server.database import Database
from server.controllers import media_catalog as media
from server.controllers.pano_controller import PanoController, create_pano_blueprint
from server.http_policies import register_http_policies


@unittest.skipUnless(os.environ.get('TEST_POSTGIS')=='1','Requires disposable PostGIS')
class MediaCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db=Database(os.environ['TEST_DATABASE_URL'])
        cls.controller=PanoController.__new__(PanoController);cls.controller.db=cls.db;cls.controller._ensure_table()
        cls.app=Flask(__name__)
        register_http_policies(cls.app,lambda token:{'uid':2 if token=='viewer' else 1} if token in {'valid','viewer'} else None,lambda _:False,lambda p:{'id':p['uid'],'role':'viewer' if p['uid']==2 else 'admin'})
        cls.app.register_blueprint(media.media_blueprint,url_prefix='/api');cls.app.register_blueprint(create_pano_blueprint(cls.controller),url_prefix='/api')
        cls.patcher=patch.object(media,'database',cls.db);cls.patcher.start()
    @classmethod
    def tearDownClass(cls):cls.patcher.stop()
    def setUp(self):
        self.client=self.app.test_client();self.client.set_cookie('access_token','valid')
        self.prefix='catalog_'+uuid4().hex
        with self.db.cursor(write=True) as c:
            c.execute('INSERT INTO panorama_folders(name) VALUES (%s) RETURNING id',(self.prefix,));self.folder=c.fetchone()['id']
        self.ids=[self.controller._insert_pano_db(self.prefix+f'_{i}.JPG','unused',43+i*.001,47,0,0,None,metadata={'media_type':'panorama','width':1024,'height':512}) for i in range(3)]
    def tearDown(self):
        with self.db.cursor(write=True) as c:
            c.execute('DELETE FROM public.photos_4326 WHERE filename LIKE %s',(self.prefix+'%',));c.execute('DELETE FROM panorama_folders WHERE name LIKE %s',(self.prefix+'%',))
    def bulk(self,action,**extra):return self.client.post('/api/media/bulk',json={'ids':self.ids,'action':action,**extra})
    def test_keyset_pagination_and_search(self):
        first=self.client.get('/api/media/catalog',query_string={'q':self.prefix,'limit':2}).json
        self.assertEqual(len(first['items']),2)
        second=self.client.get('/api/media/catalog',query_string={'q':self.prefix,'limit':2,'after':first['next_cursor']}).json
        self.assertEqual(len(second['items']),1);self.assertIsNone(second['next_cursor'])
        self.assertEqual({r['id'] for r in first['items']+second['items']},set(self.ids))
    def test_move_tags_folder_map_filters_and_empty_folder_guard(self):
        self.assertEqual(self.bulk('move',folder_id=self.folder).status_code,200)
        self.assertEqual(self.bulk('tags',tags='обследование').status_code,200)
        value=self.client.get('/api/media/catalog',query_string={'folder':self.folder}).json
        self.assertEqual(len(value['items']),3);self.assertEqual(value['items'][0]['tags'],'обследование')
        markers=self.client.get('/api/media/markers',query_string={'folder':self.folder,'west':46,'east':48,'south':42,'north':44,'zoom':20}).json
        self.assertEqual({r['id'] for r in markers},set(self.ids))
        self.assertIsNotNone(self.client.get('/api/media/bounds',query_string={'folder':self.folder}).json['bounds'])
        self.assertEqual(self.client.delete(f'/api/media/folders/{self.folder}').status_code,409)
    def test_trash_hides_markers_info_and_download_and_restore_preserves_rows(self):
        self.assertEqual(self.bulk('trash').status_code,200)
        self.assertEqual(self.client.get('/api/media/catalog',query_string={'q':self.prefix}).json['items'],[])
        trashed=self.client.get('/api/media/catalog',query_string={'q':self.prefix,'trash':'1'}).json['items'];self.assertEqual(len(trashed),3)
        self.assertEqual(self.client.get(f'/api/pano_info/{self.ids[0]}').status_code,404)
        self.assertEqual(self.client.get(f'/api/pano_info/{self.ids[0]}/download').status_code,404)
        markers=self.client.get('/api/media/markers',query_string={'q':self.prefix,'west':46,'east':48,'south':42,'north':44,'zoom':20}).json;self.assertEqual(markers,[])
        self.assertEqual(self.bulk('restore').status_code,200)
        self.assertEqual(len(self.client.get('/api/media/catalog',query_string={'q':self.prefix}).json['items']),3)
    def test_missing_ids_roll_back_whole_bulk_operation(self):
        r=self.client.post('/api/media/bulk',json={'ids':[self.ids[0],2147483647],'action':'trash'});self.assertEqual(r.status_code,404)
        with self.db.cursor() as c:
            c.execute('SELECT deleted_at FROM public.photos_4326 WHERE id=%s',(self.ids[0],));self.assertIsNone(c.fetchone()['deleted_at'])
    def test_read_only_role_cannot_change_catalog(self):
        self.client.set_cookie('access_token','viewer')
        self.assertEqual(self.client.get('/api/media/catalog').status_code,200)
        self.assertEqual(self.bulk('trash').status_code,403)
        self.assertEqual(self.client.post('/api/media/folders',json={'name':'forbidden'}).status_code,403)
    def test_invalid_bulk_shape_and_cap(self):
        self.assertEqual(self.client.post('/api/media/bulk',json=[]).status_code,400)
        self.assertEqual(self.client.post('/api/media/bulk',json={'ids':[True],'action':'trash'}).status_code,400)
        self.assertEqual(self.client.post('/api/media/bulk',json={'ids':list(range(1,502)),'action':'trash'}).status_code,400)
