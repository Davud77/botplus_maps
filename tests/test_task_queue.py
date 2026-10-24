"""Cross-kind FIFO, exclusivity and persistent dismissal against isolated PostGIS."""
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from psycopg2.extras import Json
import test_import_jobs as existing
import import_jobs as jobs

@unittest.skipUnless(os.environ.get('TEST_POSTGIS')=='1','requires isolated PostGIS')
class TaskQueueTests(unittest.TestCase):
    setUp=existing.ImportIntegrationTests.setUp
    cleanup_schema=existing.ImportIntegrationTests.cleanup_schema
    client=existing.ImportIntegrationTests.client
    enqueue=existing.ImportIntegrationTests.enqueue

    def test_fifo_across_kinds_and_no_parallel_claim(self):
        identifiers=[]
        with self.db.cursor(write=True) as cur:
            for index,(kind,table) in enumerate(jobs.TABLES.items()):
                identifier=str(uuid4());identifiers.append((identifier,kind))
                source={'root_id':'local','key':'ready.tif','title':kind,'ortho_id':1}
                if kind=='media':
                    cur.execute(f"INSERT INTO {table}(id,owner_id,source,created_at) VALUES (%s,%s,%s,NOW()+make_interval(secs=>%s))",(identifier,self.ids['editor'],Json(source),index))
                else:
                    cur.execute(f"INSERT INTO {table}(id,owner_id,idempotency_key,source,created_at) VALUES (%s,%s,%s,%s,NOW()+make_interval(secs=>%s))",(identifier,self.ids['editor'],identifier,Json(source),index))
        for identifier,kind in identifiers:
            with ThreadPoolExecutor(max_workers=3) as pool:
                claims=list(pool.map(lambda _:jobs.claim_next(self.db),range(3)))
            claimed=[j for j in claims if j]
            self.assertEqual(len(claimed),1)
            self.assertEqual((str(claimed[0]['id']),claimed[0]['_kind']),(identifier,kind))
            self.assertIsNone(jobs.claim_next(self.db))
            with self.db.cursor(write=True) as cur:
                cur.execute(f"UPDATE {jobs.TABLES[kind]} SET status='succeeded',progress=100 WHERE id=%s" if kind!='media' else "UPDATE media_import_jobs SET status='succeeded' WHERE id=%s",(identifier,))

    def test_done_is_owned_persistent_and_cannot_hide_running_job(self):
        queued=self.enqueue();identifier=queued['id']
        route=f'/api/tasks/import/{identifier}/done'
        self.assertEqual(self.editor.post(route).status_code,409)
        with self.db.cursor(write=True) as cur:
            cur.execute("UPDATE import_jobs SET status='succeeded' WHERE id=%s",(identifier,))
        self.assertEqual(self.other.post(route).status_code,404)
        self.assertEqual(self.editor.post(route).status_code,200)
        self.assertNotIn(identifier,[j['id'] for j in self.editor.get('/api/tasks').json['jobs']])
        self.assertIn(identifier,[j['id'] for j in self.admin.get('/api/tasks').json['jobs']])
        self.assertEqual(self.editor.get('/api/imports/jobs/'+identifier).status_code,200)
