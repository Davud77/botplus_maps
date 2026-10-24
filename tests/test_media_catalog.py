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
        from controllers import maps_controller
        cls.app.register_blueprint(maps_controller.maps_blueprint,url_prefix='/api')
        cls.app.register_blueprint(media.media_blueprint,url_prefix='/api');cls.app.register_blueprint(create_pano_blueprint(cls.controller),url_prefix='/api')
        cls.patcher=patch.object(media,'database',cls.db);cls.patcher.start()
    @classmethod
    def tearDownClass(cls):cls.patcher.stop()
    def setUp(self):
        self.client=self.app.test_client();self.client.set_cookie('access_token','valid')
        self.prefix='catalog_'+uuid4().hex
        with self.db.cursor(write=True) as c:
            c.execute('INSERT INTO panorama_folders(name) VALUES (%s) RETURNING id',(self.prefix,));self.folder=c.fetchone()['id']
        self.ids=[self.controller._insert_pano_db(self.prefix+f'_{i}.JPG','unused',43+i*.0001,47,0,0,None,metadata={'media_type':'panorama','width':1024,'height':512}) for i in range(3)]
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

    def test_purge_rejects_active_records_and_only_deletes_trashed_selection(self):
        self.assertEqual(self.bulk('purge').status_code,409)
        self.assertEqual(self.bulk('trash').status_code,200)
        response=self.client.post('/api/media/bulk',json={'ids':[self.ids[0]],'action':'purge'})
        self.assertEqual(response.status_code,200)
        with self.db.cursor() as c:
            c.execute('SELECT id FROM public.photos_4326 WHERE id=ANY(%s)',(self.ids,))
            self.assertEqual({r['id'] for r in c.fetchall()},set(self.ids[1:]))
        self.assertEqual(self.bulk('restore').status_code,404)

    def test_empty_trash_keeps_active_records_and_read_only_role_cannot_purge(self):
        response=self.client.post('/api/media/bulk',json={'ids':[self.ids[0]],'action':'trash'})
        self.assertEqual(response.status_code,200)
        self.client.set_cookie('access_token','viewer')
        self.assertEqual(self.client.post('/api/media/trash/empty',json={}).status_code,403)
        self.assertEqual(self.client.post('/api/media/bulk',json={'ids':[self.ids[0]],'action':'purge'}).status_code,403)
        self.client.set_cookie('access_token','valid')
        response=self.client.post('/api/media/trash/empty',json={})
        self.assertEqual(response.status_code,200)
        with self.db.cursor() as c:
            c.execute('SELECT id FROM public.photos_4326 WHERE id=ANY(%s)',(self.ids,))
            self.assertEqual({r['id'] for r in c.fetchall()},set(self.ids[1:]))

    def test_purge_removes_managed_upload_and_preserves_external_source(self):
        import config,tempfile
        from pathlib import Path
        from psycopg2.extras import Json
        with tempfile.TemporaryDirectory() as folder,patch.object(config,'MEDIA_ROOT',folder):
            managed=Path(folder)/'panoramas'/'incoming'/'test.jpg'
            managed.parent.mkdir(parents=True);managed.write_bytes(b'managed upload')
            external=Path(folder)/'external.jpg';external.write_bytes(b'NAS original')
            with self.db.cursor(write=True) as c:
                c.execute("UPDATE public.photos_4326 SET source_ref=%s WHERE id=%s",(Json({'root_id':'__media_uploads','key':'test.jpg'}),self.ids[0]))
                c.execute("UPDATE public.photos_4326 SET source_ref=%s WHERE id=%s",(Json({'root_id':'nas','key':'external.jpg'}),self.ids[1]))
            self.assertEqual(self.bulk('trash').status_code,200)
            self.assertEqual(self.bulk('purge').status_code,200)
            self.assertFalse(managed.exists());self.assertEqual(external.read_bytes(),b'NAS original')

    def test_counts_prove_deletion_even_when_next_records_fill_the_page(self):
        first=self.client.get('/api/media/catalog',query_string={'q':self.prefix,'limit':2}).json
        self.assertEqual(first['total'],3)
        response=self.client.post('/api/media/bulk',json={'ids':[first['items'][0]['id']],'action':'trash'})
        self.assertEqual(response.status_code,200);self.assertEqual(response.json['affected'],1)
        second=self.client.get('/api/media/catalog',query_string={'q':self.prefix,'limit':2}).json
        self.assertEqual(len(second['items']),2);self.assertEqual(second['total'],2)
        self.assertNotIn(first['items'][0]['id'],[i['id'] for i in second['items']])
        again=self.client.post('/api/media/bulk',json={'ids':[first['items'][0]['id']],'action':'trash'})
        self.assertEqual(again.json['affected'],0)

    def test_catalog_defaults_to_200_and_paginates_without_duplicates(self):
        with self.db.cursor(write=True) as c:
            c.execute("""INSERT INTO public.photos_4326(filename,path,geom)
                SELECT %s||n||'.jpg','unused',ST_SetSRID(ST_MakePoint(47,43,0),4326)
                FROM generate_series(1,205) n""",(self.prefix+'_page_',))
        first=self.client.get('/api/media/catalog',query_string={'q':self.prefix}).json
        self.assertEqual(len(first['items']),200);self.assertEqual(first['total'],208)
        second=self.client.get('/api/media/catalog',query_string={'q':self.prefix,'after':first['next_cursor']}).json
        self.assertEqual(len(second['items']),8)
        self.assertFalse(set(r['id'] for r in first['items'])&set(r['id'] for r in second['items']))
        capped=self.client.get('/api/media/catalog',query_string={'q':self.prefix,'limit':1000}).json
        self.assertEqual(len(capped['items']),200)

    def test_spatial_index_counts_follow_trash_restore_and_geometry_changes(self):
        self.assertEqual(self.bulk('trash').status_code,200)
        total=self.client.get('/api/media/catalog').json['total']
        self.bulk('restore')
        self.assertEqual(self.client.get('/api/media/catalog').json['total'],total+3)
        with self.db.cursor(write=True) as cur:
            cur.execute('UPDATE public.photos_4326 SET geom=ST_SetSRID(ST_MakePoint(20,10,0),4326) WHERE id=%s',(self.ids[0],))
        response=self.client.get('/api/panoramas?west=19&south=9&east=21&north=11&zoom=10&limit=50000')
        self.assertEqual(response.status_code,200)
        self.assertEqual(sum(p['count'] for p in response.json),1)
        self.assertLessEqual(len(self.client.get('/api/panoramas').json),1000)

    def test_coverage_links_nearby_survey_points_and_hides_deleted_records(self):
        with self.db.cursor(write=True) as cur:
            cur.execute('UPDATE public.photos_4326 SET directory=%s WHERE id=ANY(%s)',(self.prefix,self.ids))
        url='/api/media/coverage?west=46&south=42&east=48&north=44&zoom=14&q='+self.prefix
        geometry=self.client.get(url).json
        self.assertIn(geometry['type'],('LineString','MultiLineString'))
        self.assertTrue(geometry['coordinates'])
        self.bulk('trash')
        self.assertEqual(self.client.get(url).json['coordinates'],[])
        self.bulk('restore')
        self.assertTrue(self.client.get(url).json['coordinates'])
        with self.db.cursor(write=True) as cur:
            cur.execute('UPDATE public.photos_4326 SET geom=ST_SetSRID(ST_MakePoint(20,10,0),4326) WHERE id=%s',(self.ids[1],))
        geometry=self.client.get(url).json
        # No line may stretch from the survey area to a distant moved point.
        def vertices(value):
            if value and isinstance(value[0],(int,float)):yield value
            else:
                for child in value:yield from vertices(child)
        self.assertTrue(all(point[0]>40 for point in vertices(geometry['coordinates'])))

    def test_unfiltered_coverage_refreshes_simplified_chunks_after_trash_and_restore(self):
        with self.db.cursor(write=True) as cur:
            cur.execute('UPDATE public.photos_4326 SET directory=%s WHERE id=ANY(%s)',(self.prefix,self.ids))
        url='/api/media/coverage?west=46.999&south=43.0001&east=47.001&north=43.003&zoom=14'
        self.assertTrue(self.client.get(url).json['coordinates'])
        self.bulk('trash')
        self.assertEqual(self.client.get(url).json['coordinates'],[])
        self.bulk('restore')
        self.assertTrue(self.client.get(url).json['coordinates'])

    def test_coverage_draw_flattens_multiple_disconnected_tracks(self):
        extra=[self.controller._insert_pano_db(self.prefix+f'_other_{i}.jpg','unused',43+i*.0001,47.01,0,0,None) for i in range(2)]
        with self.db.cursor(write=True) as cur:
            cur.execute('UPDATE public.photos_4326 SET directory=%s WHERE id=ANY(%s)',(self.prefix,self.ids))
            cur.execute('UPDATE public.photos_4326 SET directory=%s WHERE id=ANY(%s)',(self.prefix+'_other',extra))
        geometry=self.client.get('/api/media/coverage?west=46.99&south=42.99&east=47.02&north=43.01&zoom=14').json
        self.assertEqual(geometry['type'],'MultiLineString')
        self.assertGreaterEqual(len(geometry['coordinates']),2)

    def test_coverage_breaks_at_gaps_and_upgrade_removes_existing_long_links(self):
        from services.panorama_coverage import initialize
        points=[(47,43),(47.00006,43),(47.001,43)]
        with self.db.cursor(write=True) as cur:
            for identifier,(lng,lat) in zip(self.ids,points):
                cur.execute('UPDATE public.photos_4326 SET directory=%s,geom=ST_SetSRID(ST_MakePoint(%s,%s,0),4326) WHERE id=%s',(self.prefix,lng,lat,identifier))
            cur.execute('SELECT from_id,to_id FROM public.panorama_coverage WHERE from_id=ANY(%s)',(self.ids,))
            self.assertEqual({(r['from_id'],r['to_id']) for r in cur.fetchall()},{(self.ids[0],self.ids[1])})
            # Simulate a product created under the previous 200-metre rule.
            cur.execute('''INSERT INTO public.panorama_coverage SELECT a.id,b.id,ST_Force2D(ST_MakeLine(a.geom,b.geom))
                FROM public.photos_4326 a,public.photos_4326 b WHERE a.id=%s AND b.id=%s''',(self.ids[1],self.ids[2]))
            cur.execute('UPDATE public.panorama_coverage_rules SET version=1 WHERE id')
            initialize(cur)
            cur.execute('SELECT count(*) AS n FROM public.panorama_coverage WHERE from_id=%s AND to_id=%s',(self.ids[1],self.ids[2]));self.assertEqual(cur.fetchone()['n'],0)
            cur.execute('SELECT version FROM public.panorama_coverage_rules WHERE id');self.assertEqual(cur.fetchone()['version'],2)
            cur.execute('SELECT max(ST_Length(geom::geography)) AS length FROM public.panorama_coverage WHERE from_id=ANY(%s)',(self.ids,));self.assertLessEqual(cur.fetchone()['length'],25)

    def test_coverage_detail_and_forced_lines_and_point_mode(self):
        with self.db.cursor(write=True) as cur:
            cur.execute('UPDATE public.photos_4326 SET directory=%s WHERE id=ANY(%s)',(self.prefix,self.ids))
        url='/api/media/coverage?west=46.99&south=42.99&east=47.01&north=43.01&zoom=19&q='+self.prefix
        self.assertEqual(self.client.get(url).json['coordinates'],[])
        for detail in ['fast','balanced','precise']:
            response=self.client.get(url+'&lines=1&detail='+detail)
            self.assertEqual(response.status_code,200);self.assertTrue(response.json['coordinates'])
        self.assertEqual(self.client.get(url+'&lines=1&detail=bad').status_code,400)
        response=self.client.get('/api/media/markers?west=46&south=42&east=48&north=44&zoom=12&points=1&q='+self.prefix)
        self.assertEqual(len(response.json),3);self.assertTrue(all(row['count']==1 for row in response.json))

    def test_background_rebuild_preserves_original_edges(self):
        from services.panorama_coverage import rebuild
        from unittest.mock import Mock
        with self.db.cursor(write=True) as cur:
            cur.execute('UPDATE public.photos_4326 SET directory=%s WHERE id=ANY(%s)',(self.prefix,self.ids))
            cur.execute('SELECT from_id,to_id,ST_AsText(geom) AS geom FROM public.panorama_coverage ORDER BY from_id');before=cur.fetchall()
        lease=Mock();result=rebuild(self.db,lease)
        self.assertGreater(result['chunks'],0);lease.check.assert_called_once()
        with self.db.cursor() as cur:
            cur.execute('SELECT from_id,to_id,ST_AsText(geom) AS geom FROM public.panorama_coverage ORDER BY from_id');self.assertEqual(cur.fetchall(),before)
            cur.execute('SELECT count(*) AS n FROM public.panorama_coverage_draw WHERE NOT ST_IsEmpty(geom)');self.assertEqual(cur.fetchone()['n'],result['chunks'])
        with patch('import_jobs.enqueue_operation',return_value={'id':'queued'}) as enqueue,patch('import_jobs.serialize',side_effect=lambda value:value):
            response=self.client.post('/api/media/coverage/rebuild',json={})
            self.assertEqual(response.status_code,202);self.assertEqual(response.json['job']['id'],'queued')
            self.assertEqual(enqueue.call_args.args[1],'panorama-coverage')
        self.client.set_cookie('access_token','viewer')
        self.assertEqual(self.client.post('/api/media/coverage/rebuild',json={}).status_code,403)

    def test_anonymous_panorama_image_and_info_hide_storage_details_and_trash(self):
        import tempfile
        from pathlib import Path
        from controllers import maps_controller
        from controllers.pano_controller import PanoController as PublicController
        anonymous=self.app.test_client();base='/api/public/maps/published/panoramas/'
        with tempfile.TemporaryDirectory() as folder,patch.object(maps_controller,'publication',return_value={'config':{'show_panoramas':True}}),patch.object(maps_controller,'Database',return_value=self.db):
            image=Path(folder)/'pano.jpg';image.write_bytes(b'test-public-image')
            with patch.object(PublicController,'source_file',return_value=str(image)):
                response=anonymous.get(base+str(self.ids[0]));self.assertEqual(response.status_code,200)
                self.assertNotIn('source_ref',response.json);self.assertNotIn('directory',response.json);self.assertNotIn('filename',response.json)
                response=anonymous.get(base+str(self.ids[0])+'/image');self.assertEqual(response.status_code,200);self.assertEqual(response.data,b'test-public-image');self.assertEqual(response.headers['Cache-Control'],'no-store');response.close()
                self.bulk('trash')
                self.assertEqual(anonymous.get(base+str(self.ids[0])).status_code,404)
                self.assertEqual(anonymous.get(base+str(self.ids[0])+'/image').status_code,404)
                self.assertEqual(anonymous.delete(base+str(self.ids[0])).status_code,401)
