"""Separate-process integration probe; do not import into the unittest runner."""
from gevent import monkey
monkey.patch_all()

import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gevent
from gevent.event import Event
from psycopg2 import extensions
from server.database import Database

db = Database(os.environ["TEST_DATABASE_URL"])
gate, tick = Event(), Event()
pids, resources = [], []


def query():
    with db.cursor() as cursor:
        resources.append(cursor.connection)
        cursor.execute("SELECT pg_backend_pid() AS pid")
        pids.append(cursor.fetchone()["pid"])
        if len(pids) == 2:
            gate.set()
        assert gate.wait(timeout=3), "database operations did not overlap"
        cursor.execute("SELECT pg_sleep(.2)")
        assert tick.is_set(), "libpq blocked the gevent event loop"


def ticker():
    gate.wait(timeout=3)
    gevent.sleep(.02)
    tick.set()


jobs = [gevent.spawn(query), gevent.spawn(query), gevent.spawn(ticker)]
gevent.joinall(jobs, timeout=5, raise_error=True)
assert all(job.ready() for job in jobs), "greenlet timeout"
assert len(set(pids)) == 2, "greenlets shared a PostgreSQL session"
assert all(connection.closed for connection in resources), "connection leak"
assert extensions.get_wait_callback() is not None, "cooperative libpq callback missing"
print("gevent isolation passed")
