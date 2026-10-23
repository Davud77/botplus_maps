"""Real SQL authorization, session revocation and published map boundaries."""
import os
from pathlib import Path
import sys
import unittest
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from uuid import uuid4
from flask import Flask, Response, jsonify
from psycopg2 import sql, extensions
from werkzeug.security import generate_password_hash
from werkzeug.exceptions import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))
from database import Database
from init_pg_auth import init_auth_db
from services.auth_service import create_access_token, decode_access_token
from services.permissions import resolve_session
from services import map_settings
from controllers import settings_controller
from repositories import user_repository
from controllers import account_controller as accounts, maps_controller as maps, vector
from controllers.auth_controller import auth_blueprint
from http_policies import register_http_policies


@unittest.skipUnless(os.environ.get('TEST_POSTGIS') == '1', 'requires isolated PostGIS test database')
class WorkspaceIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.root = Database(os.environ['TEST_DATABASE_URL'])
        self.schema = 'workspace_' + uuid4().hex
        with self.root.cursor(write=True) as cur:
            cur.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(self.schema)))
        self.addCleanup(self.cleanup_schema)
        self.dsn = extensions.make_dsn(os.environ['TEST_DATABASE_URL'], options=f'-c search_path={self.schema},public')
        self.db = Database(self.dsn)
        with patch.dict(os.environ, {'DATABASE_URL': self.dsn}):
            init_auth_db()
        password = generate_password_hash('initial-test-password')
        with self.db.cursor(write=True) as cur:
            cur.execute("INSERT INTO users (username,password,role) VALUES ('admin',%s,'admin'),('editor',%s,'editor'),('viewer',%s,'viewer'),('other',%s,'editor') RETURNING id,username", (password,)*4)
            self.ids = {row['username']: row['id'] for row in cur.fetchall()}
            cur.execute('CREATE TABLE orthophotos (id INTEGER PRIMARY KEY)')
            cur.execute('INSERT INTO orthophotos VALUES (1),(2)')
            cur.execute("CREATE TABLE roads (id SERIAL PRIMARY KEY, label TEXT, geom geometry(Point,4326))")
            cur.execute("INSERT INTO roads (label,geom) VALUES ('published object',ST_SetSRID(ST_MakePoint(47,43),4326))")
        for module in [accounts, maps, user_repository, map_settings, settings_controller]:
            patcher = patch.object(module, 'Database', return_value=self.db)
            patcher.start(); self.addCleanup(patcher.stop)
        patcher = patch.object(vector, 'database', self.db)
        patcher.start(); self.addCleanup(patcher.stop)
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        @self.app.errorhandler(HTTPException)
        def api_error(error):
            return jsonify(message=error.description), error.code
        register_http_policies(self.app, decode_access_token, lambda origin: False, resolve_session)
        self.app.register_blueprint(settings_controller.settings_blueprint, url_prefix='/api')
        self.app.register_blueprint(accounts.account_blueprint, url_prefix='/api')
        self.app.register_blueprint(maps.maps_blueprint, url_prefix='/api')
        self.app.register_blueprint(auth_blueprint, url_prefix='/api/auth')
        self.app.add_url_rule('/api/upload', view_func=lambda: jsonify(ok=True), methods=['POST'])
        self.app.add_url_rule('/test-raster', endpoint='ortho.get_ortho_tile', view_func=lambda *args, **kwargs: Response(b'tile', mimetype='image/png'))
        self.admin, self.editor, self.viewer, self.other = [self.client(role) for role in ['admin','editor','viewer','other']]

    def cleanup_schema(self):
        with self.root.cursor(write=True) as cur:
            cur.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(self.schema)))

    def client(self, name):
        client = self.app.test_client()
        client.set_cookie('access_token', create_access_token({'uid': self.ids[name], 'u': name, 'ver': 0}, expires_in=300))
        return client

    def create_map(self, client=None, **extra):
        response = (client or self.editor).post('/api/maps', json={'title': 'Project map', **extra})
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        return response.get_json()['map']

    def publish(self, record, published=True):
        response = self.editor.post(f"/api/maps/{record['id']}/publication", json={'published': published,'revision': record['revision']})
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.get_json()['map']

    def test_viewer_and_editor_cannot_escalate_privileges(self):
        for client in [self.viewer,self.editor]:
            self.assertEqual(client.get('/api/users').status_code,403)
            self.assertEqual(client.post('/api/users',json={'role':'admin'}).status_code,403)
            self.assertEqual(client.patch(f"/api/users/{self.ids['viewer']}",json={'role':'admin'}).status_code,403)
        self.assertEqual(self.viewer.post('/api/maps',json={'title':'forbidden'}).status_code,403)
        self.assertEqual(self.viewer.post('/api/upload').status_code,403)
        self.assertEqual(self.viewer.get('/api/maps').status_code,200)

    def test_only_owner_or_admin_can_edit_and_publish_map(self):
        record = self.create_map()
        for client in [self.viewer,self.other]:
            self.assertEqual(client.put(f"/api/maps/{record['id']}",json={}).status_code,403)
            self.assertEqual(client.post(f"/api/maps/{record['id']}/publication",json={'published':True,'revision':1}).status_code,403)
        self.assertEqual(self.admin.get(f"/api/maps/{record['id']}").status_code,200)

    def test_password_change_requires_current_password_and_revokes_old_sessions(self):
        old = self.client('viewer')
        self.assertEqual(self.viewer.post('/api/account/password',json={'current_password':'wrong','new_password':'new-test-password'}).status_code,400)
        response = self.viewer.post('/api/account/password',json={'current_password':'initial-test-password','new_password':' new-test-password '})
        self.assertEqual(response.status_code,200)
        self.assertEqual(old.get('/api/maps').status_code,401)
        self.assertTrue(self.viewer.get('/api/auth/me').get_json()['authenticated'])
        anonymous = self.app.test_client()
        self.assertEqual(anonymous.post('/api/auth/login',json={'username':'viewer','password':'initial-test-password'}).status_code,401)
        self.assertEqual(anonymous.post('/api/auth/login',json={'username':'viewer','password':' new-test-password '}).status_code,200)

    def test_user_creation_and_role_changes_take_effect_without_relogin(self):
        response = self.admin.post('/api/users',json={'username':'colleague','password':'colleague-test-password','role':'editor'})
        self.assertEqual(response.status_code,201)
        self.assertNotIn('password', response.get_json()['user'])
        duplicate = self.admin.post('/api/users',json={'username':'colleague','password':'colleague-test-password','role':'editor'})
        self.assertEqual(duplicate.status_code,409)
        self.assertEqual(self.admin.patch(f"/api/users/{self.ids['editor']}",json={'role':'viewer'}).status_code,200)
        self.assertEqual(self.editor.post('/api/maps',json={'title':'no longer allowed'}).status_code,403)
        self.assertEqual(self.admin.patch(f"/api/users/{self.ids['editor']}",json={'is_active':False}).status_code,200)
        self.assertEqual(self.editor.get('/api/maps').status_code,401)
        self.admin.patch(f"/api/users/{self.ids['editor']}",json={'is_active':True})
        self.assertEqual(self.editor.get('/api/maps').status_code,401)

    def test_last_admin_cannot_be_demoted_or_disabled(self):
        for change in [{'role':'viewer'},{'is_active':False}]:
            self.assertEqual(self.admin.patch(f"/api/users/{self.ids['admin']}",json=change).status_code,409)

    def test_concurrent_admin_demotion_leaves_one_active_admin(self):
        with self.db.cursor(write=True) as cur:
            cur.execute("UPDATE users SET role='admin' WHERE username='editor'")
        barrier = threading.Barrier(2)
        def demote(name):
            client = self.client(name)
            barrier.wait(timeout=10)
            return client.patch(f"/api/users/{self.ids[name]}",json={'role':'editor'}).status_code
        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(demote,['admin','editor']))
        self.assertEqual(sorted(results),[200,409])
        with self.db.cursor() as cur:
            cur.execute("SELECT count(*) AS count FROM users WHERE role='admin' AND is_active")
            self.assertEqual(cur.fetchone()['count'],1)

    def test_map_revisions_and_published_snapshot_are_independent(self):
        record = self.create_map()
        published = self.publish(record)
        anonymous = self.app.test_client()
        slug = published['public_slug']
        update = {'title':'New draft title','description':'','config':record['config'],'revision':published['revision']}
        response = self.editor.put(f"/api/maps/{record['id']}",json=update)
        self.assertEqual(response.status_code,200,response.get_data(as_text=True))
        self.assertEqual(self.editor.put(f"/api/maps/{record['id']}",json=update).status_code,409)
        self.assertEqual(anonymous.get(f'/api/public/maps/{slug}').get_json()['map']['title'],'Project map')
        refreshed = self.publish(response.get_json()['map'])
        self.assertEqual(anonymous.get(f'/api/public/maps/{slug}').get_json()['map']['title'],'New draft title')
        disabled = self.publish(refreshed,False)
        self.assertEqual(anonymous.get(f'/api/public/maps/{slug}').status_code,404)
        new = self.publish(disabled)
        self.assertNotEqual(new['public_slug'],slug)

    def test_publication_exposes_only_selected_tiles_not_catalog_or_originals(self):
        db_name = extensions.parse_dsn(self.dsn)['dbname']
        config = {'orthophoto_ids':[1], 'vector_layers':[{'dbName':db_name,'schema':self.schema,'tableName':'roads'}]}
        record = self.publish(self.create_map(config=config))
        slug = record['public_slug']
        anonymous = self.app.test_client()
        info = anonymous.get(f'/api/public/maps/{slug}')
        self.assertEqual(info.status_code,200)
        self.assertNotIn('dbName',info.get_data(as_text=True))
        prefix = f'/api/public/maps/{slug}'
        raster = anonymous.get(prefix+'/orthophotos/1/tiles/0/0/0.png')
        self.assertEqual(raster.status_code,200)
        self.assertEqual(raster.headers['Cache-Control'],'no-store')
        self.assertEqual(anonymous.get(prefix+'/orthophotos/1/tiles/0/0/0@2x.png').status_code,200)
        self.assertEqual(anonymous.get(prefix+'/orthophotos/2/tiles/0/0/0@2x.png').status_code,404)
        self.assertEqual(anonymous.get(prefix+'/orthophotos/2/tiles/0/0/0.png').status_code,404)
        self.assertEqual(anonymous.get(prefix+'/orthophotos/1/tiles/0/0/0@2x.webp').status_code,200)
        self.assertEqual(anonymous.get(prefix+'/orthophotos/2/tiles/0/0/0@2x.webp').status_code,404)
        self.assertEqual(anonymous.get(prefix+'/vectors/1/tiles/0/0/0.pbf').status_code,404)
        mvt = anonymous.get(prefix+'/vectors/0/tiles/0/0/0.pbf')
        self.assertEqual(mvt.status_code,200,mvt.data)
        self.assertTrue(mvt.data)
        self.assertEqual(anonymous.get(prefix+'/vectors/0/tiles/25/0/0.pbf').status_code,404)
        self.assertEqual(anonymous.get('/api/maps').status_code,401)
        self.assertEqual(anonymous.get('/api/orthophotos/1/download').status_code,401)
        self.assertEqual(anonymous.post(prefix,json={}).status_code,401)

    def test_invalid_map_config_cannot_point_to_secret_tables_or_external_urls(self):
        for config in [{'base_layer':'https://attacker.example'},{'view':{'center':[999,0],'zoom':5}},
                       {'view':{'center':[0,0],'zoom':True}}, {'orthophoto_ids':[True]},
                       {'vector_layers':[{'dbName':extensions.parse_dsn(self.dsn)['dbname'],'schema':self.schema,'tableName':'users'}]}]:
            with self.subTest(config=config):
                self.assertEqual(self.editor.post('/api/maps',json={'title':'invalid','config':config}).status_code,400)

    def test_panorama_catalog_is_not_accidentally_published(self):
        record = self.create_map(config={'show_panoramas':True})
        response = self.editor.post(f"/api/maps/{record['id']}/publication",json={'published':True,'revision':1})
        self.assertEqual(response.status_code,400)

    def test_settings_permissions_custom_catalogs_and_defaults(self):
        for client in [self.viewer,self.editor]:
            self.assertEqual(client.get('/api/settings/map').status_code,200)
            self.assertEqual(client.post('/api/settings/basemaps',json={}).status_code,403)
            self.assertEqual(client.post('/api/settings/coordinate-systems',json={}).status_code,403)
        self.assertEqual(self.viewer.patch('/api/account/preferences',json={'theme':'dark'}).status_code,200)
        self.assertEqual(self.viewer.get('/api/auth/me').get_json()['user']['theme'],'dark')
        self.assertEqual(self.viewer.patch('/api/account/preferences',json={'theme':'wrong'}).status_code,400)
        crs=self.admin.post('/api/settings/coordinate-systems',json={'name':'Local UTM','definition':'+proj=utm +zone=38 +datum=WGS84 +units=m +no_defs'})
        self.assertEqual(crs.status_code,201,crs.get_data(as_text=True))
        code=crs.get_json()['coordinate_system']['id']
        point=self.viewer.get('/api/settings/coordinates',query_string={'crs':code,'lat':43,'lng':45})
        self.assertEqual(point.status_code,200)
        self.assertAlmostEqual(point.get_json()['x'],500000,places=2)
        for bad in ['https://bad.example/crs','+proj=utm +zone=38 +nadgrids=/etc/passwd','EPSG:9999999']:
            self.assertEqual(self.admin.post('/api/settings/coordinate-systems',json={'name':'Bad','definition':bad}).status_code,400)
        base=self.admin.post('/api/settings/basemaps',json={'name':'Local tiles','url':'http://localhost:8080/{z}/{x}/{y}.png','scheme':'tms','attribution':'<img onerror=alert(1)>'})
        self.assertEqual(base.status_code,201,base.get_data(as_text=True))
        base=base.get_json()['basemap']
        self.assertNotIn('<',base['attribution'])
        self.assertEqual(self.admin.patch('/api/settings/map/defaults',json={'basemap':base['id'],'coordinate_system':code}).status_code,200)
        created=self.create_map()
        self.assertEqual(created['config']['base_layer'],base['id'])
        self.assertEqual(created['config']['coordinate_system'],code)
        public=self.publish(created)
        config=self.app.test_client().get('/api/public/maps/'+public['public_slug']).get_json()['map']['config']
        self.assertEqual(config['base_layer_definition']['url'],base['url'])
        for bad in ['javascript:alert(1)','https://host/{z}/{x}/{q}','https://host/{z}/{x}/{y}/{evil}','https://host/{z}/{x}/{y}/}','http://u:p@host/{z}/{x}/{y}']:
            self.assertEqual(self.admin.post('/api/settings/basemaps',json={'name':'Bad','url':bad}).status_code,400)

    def test_layer_presentation_survives_save_and_publication(self):
        config={'orthophoto_ids':[1,2], 'layer_settings':[{'key':'ortho:2','visible':False,'opacity':0.3},{'key':'ortho:1','opacity':0.75}]}
        created=self.create_map(config=config)
        public=self.publish(created)
        actual=self.app.test_client().get('/api/public/maps/'+public['public_slug']).get_json()['map']['config']
        self.assertEqual(actual['layer_settings'],config['layer_settings'])
        for bad in [[{'key':'ortho:3'}],[{'key':'ortho:1','opacity':2}],[{'key':'ortho:1','style':{'color':'red'}}],[{'key':'ortho:1','visible':'false'}],[{'key':'ortho:1'},{'key':'ortho:1'}]]:
            self.assertEqual(self.editor.put('/api/maps/'+created['id'],json={'title':'Bad style','revision':public['revision'],'config':{**config,'layer_settings':bad}}).status_code,400)

    def test_basemap_order_visibility_and_per_layer_coordinates_are_persisted(self):
        db_name=extensions.parse_dsn(self.dsn)['dbname']
        config={'base_layer':'google_maps','orthophoto_ids':[1],
                'vector_layers':[{'dbName':db_name,'schema':self.schema,'tableName':'roads'}],
                'layer_settings':[{'key':'vector:0','coordinate_system':'EPSG:32638'},
                                  {'key':'basemap','visible':False,'opacity':0.45,'coordinate_system':'EPSG:3857'},
                                  {'key':'ortho:1','coordinate_system':'EPSG:4326'}]}
        record=self.publish(self.create_map(config=config))
        anonymous=self.app.test_client()
        base='/api/public/maps/'+record['public_slug']
        published=anonymous.get(base).get_json()['map']['config']
        self.assertEqual(published['layer_settings'],config['layer_settings'])
        self.assertNotIn('dbName',anonymous.get(base).get_data(as_text=True))
        coordinates=anonymous.get(base+'/coordinates/vector:0',query_string={'lat':43,'lng':45})
        self.assertEqual(coordinates.status_code,200)
        self.assertAlmostEqual(coordinates.get_json()['x'],500000,places=2)
        self.assertEqual(anonymous.get(base+'/coordinates/vector:1?lat=43&lng=45').status_code,404)
        self.assertEqual(anonymous.get(base+'/coordinates/ortho:2?lat=43&lng=45').status_code,404)
        for layer in [{'key':'basemap','coordinate_system':'EPSG:9999999'}, {'key':'basemap','coordinate_system':None}]:
            self.assertEqual(self.editor.post('/api/maps',json={'title':'Invalid CRS','config':{**config,'layer_settings':[layer]}}).status_code,400)
        self.assertEqual(self.editor.post('/api/maps',json={'title':'Missing background','config':{'base_layer':'none','layer_settings':[{'key':'basemap'}]}}).status_code,400)
