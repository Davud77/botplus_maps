"""Short surveyed-track segments; never bridge distant or unrelated surveys."""
import json,math,time
from collections import OrderedDict
from flask import jsonify,request,abort
from services.panorama_index import viewport
_cache=OrderedDict()
MAX_SIMPLIFICATION_DEGREES=5.0/111320
COVERAGE_RULES_VERSION=2


def initialize(cur):
    cur.execute("SELECT to_regclass('public.panorama_coverage') AS name")
    row=cur.fetchone();fresh=(row['name'] if isinstance(row,dict) else row[0]) is None
    cur.execute('''CREATE OR REPLACE FUNCTION public.panorama_track_key(source jsonb,directory text) RETURNS text
        LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$ SELECT coalesce(source->>'root_id','managed')||':'||
        coalesce(regexp_replace(source->>'key','[^/]+$',''),directory,'') $$''')
    cur.execute('''CREATE INDEX IF NOT EXISTS photos_track_id_idx ON public.photos_4326
        (public.panorama_track_key(source_ref,directory),id) WHERE deleted_at IS NULL''')
    cur.execute('''CREATE TABLE IF NOT EXISTS public.panorama_coverage (
        from_id int NOT NULL,to_id int NOT NULL,geom geometry(LineString,4326) NOT NULL,PRIMARY KEY(from_id,to_id))''')
    cur.execute('CREATE INDEX IF NOT EXISTS panorama_coverage_geom_idx ON public.panorama_coverage USING gist(geom)')
    cur.execute('CREATE INDEX IF NOT EXISTS panorama_coverage_chunk_idx ON public.panorama_coverage((from_id/256))')
    cur.execute('CREATE INDEX IF NOT EXISTS panorama_coverage_to_idx ON public.panorama_coverage(to_id)')
    if fresh:
        cur.execute('''INSERT INTO public.panorama_coverage
            SELECT previous,id,ST_Force2D(ST_MakeLine(previous_geom,geom)) FROM (
              SELECT id,geom,"timestamp",lag(id) OVER track AS previous,lag(geom) OVER track AS previous_geom,
              lag("timestamp") OVER track AS previous_time FROM public.photos_4326 WHERE deleted_at IS NULL AND geom IS NOT NULL
              WINDOW track AS (PARTITION BY public.panorama_track_key(source_ref,directory) ORDER BY id)) points
            WHERE previous IS NOT NULL AND ST_DistanceSphere(previous_geom,geom) BETWEEN .2 AND 25
            AND ("timestamp" IS NULL OR previous_time IS NULL OR abs(extract(epoch FROM "timestamp"-previous_time))<=900)''')
    cur.execute('''CREATE OR REPLACE FUNCTION public.panorama_link(a int,b int) RETURNS void LANGUAGE sql AS $$
        INSERT INTO public.panorama_coverage SELECT p.id,q.id,ST_Force2D(ST_MakeLine(p.geom,q.geom))
        FROM public.photos_4326 p,public.photos_4326 q WHERE p.id=a AND q.id=b AND p.deleted_at IS NULL AND q.deleted_at IS NULL
        AND p.geom IS NOT NULL AND q.geom IS NOT NULL AND ST_DistanceSphere(p.geom,q.geom) BETWEEN .2 AND 25
        AND (p."timestamp" IS NULL OR q."timestamp" IS NULL OR abs(extract(epoch FROM p."timestamp"-q."timestamp"))<=900)
        ON CONFLICT DO NOTHING $$''')
    cur.execute('''CREATE OR REPLACE FUNCTION public.panorama_coverage_change() RETURNS trigger
        LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
        DECLARE k text;identifier int;before_id int;after_id int;
        BEGIN
          IF TG_OP<>'INSERT' THEN
            DELETE FROM public.panorama_coverage WHERE from_id=OLD.id OR to_id=OLD.id;
            k:=public.panorama_track_key(OLD.source_ref,OLD.directory);identifier:=OLD.id;
            SELECT id INTO before_id FROM public.photos_4326 WHERE deleted_at IS NULL AND geom IS NOT NULL AND public.panorama_track_key(source_ref,directory)=k AND id<identifier ORDER BY id DESC LIMIT 1;
            SELECT id INTO after_id FROM public.photos_4326 WHERE deleted_at IS NULL AND geom IS NOT NULL AND public.panorama_track_key(source_ref,directory)=k AND id>identifier ORDER BY id LIMIT 1;
            PERFORM public.panorama_link(before_id,after_id);
          END IF;
          IF TG_OP<>'DELETE' AND NEW.deleted_at IS NULL AND NEW.geom IS NOT NULL THEN
            k:=public.panorama_track_key(NEW.source_ref,NEW.directory);identifier:=NEW.id;
            SELECT id INTO before_id FROM public.photos_4326 WHERE deleted_at IS NULL AND geom IS NOT NULL AND public.panorama_track_key(source_ref,directory)=k AND id<identifier ORDER BY id DESC LIMIT 1;
            SELECT id INTO after_id FROM public.photos_4326 WHERE deleted_at IS NULL AND geom IS NOT NULL AND public.panorama_track_key(source_ref,directory)=k AND id>identifier ORDER BY id LIMIT 1;
            DELETE FROM public.panorama_coverage WHERE from_id=before_id AND to_id=after_id;
            PERFORM public.panorama_link(before_id,identifier);PERFORM public.panorama_link(identifier,after_id);
          END IF;
          RETURN NULL;
        END $$''')
    cur.execute('''CREATE OR REPLACE TRIGGER panorama_coverage_change AFTER INSERT OR DELETE OR UPDATE OF geom,deleted_at,source_ref,directory,"timestamp"
        ON public.photos_4326 FOR EACH ROW EXECUTE FUNCTION public.panorama_coverage_change()''')

    cur.execute('''CREATE OR REPLACE FUNCTION public.panorama_index_clear() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          TRUNCATE public.panorama_spatial_cells,public.panorama_coverage,public.panorama_coverage_draw,public.panorama_coverage_dirty;
          UPDATE public.panorama_catalog_totals SET active=0,trash=0,version=version+1 WHERE id;
          RETURN NULL;
        END $$''')
    cur.execute('CREATE OR REPLACE TRIGGER panorama_index_clear AFTER TRUNCATE ON public.photos_4326 FOR EACH STATEMENT EXECUTE FUNCTION public.panorama_index_clear()')

    cur.execute("SELECT to_regclass('public.panorama_coverage_draw') AS name")
    row=cur.fetchone();fresh_draw=(row['name'] if isinstance(row,dict) else row[0]) is None
    cur.execute('''CREATE TABLE IF NOT EXISTS public.panorama_coverage_draw (
        level smallint NOT NULL,chunk bigint NOT NULL,geom geometry(Geometry,4326) NOT NULL,PRIMARY KEY(level,chunk))''')
    cur.execute('CREATE INDEX IF NOT EXISTS panorama_coverage_draw_geom_idx ON public.panorama_coverage_draw USING gist(geom)')
    cur.execute('CREATE TABLE IF NOT EXISTS public.panorama_coverage_dirty(level smallint NOT NULL,chunk bigint NOT NULL,PRIMARY KEY(level,chunk))')
    if fresh_draw:
        cur.execute('''INSERT INTO public.panorama_coverage_draw
            SELECT level,from_id/256,ST_Simplify(ST_LineMerge(ST_CollectionExtract(ST_Collect(geom),2)),LEAST(360.0/(256*power(2,level+3))*.7,5.0/111320))
            FROM public.panorama_coverage CROSS JOIN unnest(ARRAY[0,4,8,12,16]) level GROUP BY 1,2''')
    cur.execute('''CREATE OR REPLACE FUNCTION public.panorama_coverage_dirty() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE identifier int;
        BEGIN
          IF TG_OP='DELETE' THEN identifier:=OLD.from_id;ELSE identifier:=NEW.from_id;END IF;
          INSERT INTO public.panorama_coverage_dirty SELECT level,identifier/256 FROM unnest(ARRAY[0,4,8,12,16]) level ON CONFLICT DO NOTHING;
          RETURN NULL;
        END $$''')
    cur.execute('CREATE OR REPLACE TRIGGER panorama_coverage_dirty AFTER INSERT OR DELETE OR UPDATE ON public.panorama_coverage FOR EACH ROW EXECUTE FUNCTION public.panorama_coverage_dirty()')

    cur.execute('CREATE TABLE IF NOT EXISTS public.panorama_coverage_rules(id BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK(id),version INTEGER NOT NULL)')
    cur.execute('SELECT version FROM public.panorama_coverage_rules WHERE id')
    row=cur.fetchone();version=(row['version'] if isinstance(row,dict) else row[0]) if row else 0
    if version<COVERAGE_RULES_VERSION:
        # Upgrade existing products as well as future links. No original is changed.
        cur.execute('DELETE FROM public.panorama_coverage WHERE ST_Length(geom::geography)>25')
        cur.execute('TRUNCATE public.panorama_coverage_draw,public.panorama_coverage_dirty')
        cur.execute('''INSERT INTO public.panorama_coverage_draw
            SELECT level,from_id/256,ST_Simplify(ST_LineMerge(ST_CollectionExtract(ST_Collect(geom),2)),LEAST(360.0/(256*power(2,level+3))*.7,5.0/111320))
            FROM public.panorama_coverage CROSS JOIN unnest(ARRAY[0,4,8,12,16]) level GROUP BY 1,2''')
        cur.execute('UPDATE public.panorama_catalog_totals SET version=version+1 WHERE id')
        cur.execute('INSERT INTO public.panorama_coverage_rules VALUES (TRUE,%s) ON CONFLICT(id) DO UPDATE SET version=excluded.version',(COVERAGE_RULES_VERSION,))


def coverage(db,where='deleted_at IS NULL',values=None):
    west,south,east,north,zoom=viewport()
    if zoom>=18 and request.args.get('lines')!='1':return jsonify(type='MultiLineString',coordinates=[])
    detail=request.args.get('detail','fast')
    if detail not in {'fast','balanced','precise'}:abort(400)
    with db.cursor(write=True) as cur:
        cur.execute('SET LOCAL statement_timeout=5000')
        cur.execute('SELECT version FROM public.panorama_catalog_totals WHERE id');version=cur.fetchone()['version']
        key=(db._dsn,west,south,east,north,zoom,where,tuple(values or []),version,detail)
        cached=_cache.get(key)
        if cached and time.monotonic()-cached[0]<30:return jsonify(cached[1])
        params=[west,south,east,north]
        extra=''
        if where!='deleted_at IS NULL' or values:
            extra=' AND from_id IN (SELECT id FROM public.photos_4326 WHERE '+where+') AND to_id IN (SELECT id FROM public.photos_4326 WHERE '+where+')'
            params+=list(values or [])*2
        tolerance=min(360/(256*2**zoom)*.7,({'fast':5,'balanced':2,'precise':.2}[detail])/111320)
        if not extra:
            level=16 if detail!='fast' else min(16,(zoom//4)*4)
            cur.execute('''SELECT d.chunk FROM public.panorama_coverage_dirty d
                LEFT JOIN public.panorama_coverage_draw p ON p.level=d.level AND p.chunk=d.chunk
                WHERE d.level=%s AND (p.geom && ST_MakeEnvelope(%s,%s,%s,%s,4326) OR EXISTS(
                  SELECT 1 FROM public.panorama_coverage c WHERE c.from_id>=d.chunk*256 AND c.from_id<(d.chunk+1)*256
                    AND c.geom && ST_MakeEnvelope(%s,%s,%s,%s,4326))) LIMIT 256 FOR UPDATE OF d SKIP LOCKED''',[level]+params+params)
            chunks=[r['chunk'] for r in cur.fetchall()]
            if chunks:
                cur.execute('DELETE FROM public.panorama_coverage_draw WHERE level=%s AND chunk=ANY(%s)',(level,chunks))
                cur.execute('''INSERT INTO public.panorama_coverage_draw SELECT %s,from_id/256,
                    ST_Simplify(ST_LineMerge(ST_CollectionExtract(ST_Collect(geom),2)),%s) FROM public.panorama_coverage
                    WHERE from_id/256=ANY(%s) GROUP BY from_id/256''',(level,min(360/(256*2**(level+3))*.7,MAX_SIMPLIFICATION_DEGREES),chunks))
                cur.execute('DELETE FROM public.panorama_coverage_dirty WHERE level=%s AND chunk=ANY(%s)',(level,chunks))
            cur.execute('''SELECT ST_AsGeoJSON(ST_Simplify(ST_LineMerge(ST_CollectionExtract(ST_Collect(geom),2)),%s),6) AS geometry
                FROM public.panorama_coverage_draw WHERE level=%s AND geom && ST_MakeEnvelope(%s,%s,%s,%s,4326)''',[tolerance,level]+params)
        else:
            cur.execute('''SELECT ST_AsGeoJSON(ST_Simplify(ST_LineMerge(ST_CollectionExtract(ST_Collect(geom),2)),%s),6) AS geometry
                FROM public.panorama_coverage WHERE geom && ST_MakeEnvelope(%s,%s,%s,%s,4326)'''+extra,[tolerance]+params)
        row=cur.fetchone();geometry=json.loads(row['geometry']) if row['geometry'] else {'type':'MultiLineString','coordinates':[]}
    _cache[key]=(time.monotonic(),geometry)
    while len(_cache)>64:_cache.popitem(last=False)
    return jsonify(geometry)


def refresh(db=None,limit=32):
    from database import Database
    db=db or Database()
    with db.cursor(write=True) as cur:
        cur.execute('SELECT level,chunk FROM public.panorama_coverage_dirty ORDER BY level,chunk LIMIT %s FOR UPDATE SKIP LOCKED',(limit,))
        rows=cur.fetchall()
        for level in sorted({r['level'] for r in rows}):
            chunks=[r['chunk'] for r in rows if r['level']==level]
            cur.execute('DELETE FROM public.panorama_coverage_draw WHERE level=%s AND chunk=ANY(%s)',(level,chunks))
            cur.execute('''INSERT INTO public.panorama_coverage_draw SELECT %s,from_id/256,
                ST_Simplify(ST_LineMerge(ST_CollectionExtract(ST_Collect(geom),2)),%s) FROM public.panorama_coverage
                WHERE from_id/256=ANY(%s) GROUP BY from_id/256''',(level,min(360/(256*2**(level+3))*.7,MAX_SIMPLIFICATION_DEGREES),chunks))
            cur.execute('DELETE FROM public.panorama_coverage_dirty WHERE level=%s AND chunk=ANY(%s)',(level,chunks))
        return len(rows)


def rebuild(db,lease):
    """Build derived geometry in the shared FIFO queue; preserve original tracks."""
    lease.progress(10,'Построение покрытия панорам',record=True)
    with db.cursor(write=True) as cur:
        cur.execute('LOCK TABLE public.panorama_coverage IN SHARE MODE')
        cur.execute('''CREATE TEMP TABLE rebuilt_panorama_draw ON COMMIT DROP AS
            SELECT level,from_id/256 AS chunk,ST_Simplify(ST_LineMerge(ST_CollectionExtract(ST_Collect(geom),2)),
                LEAST(360.0/(256*power(2,level+3))*.7,5.0/111320)) AS geom
            FROM public.panorama_coverage CROSS JOIN unnest(ARRAY[0,4,8,12,16]) level GROUP BY 1,2''')
        lease.check()
        cur.execute('SELECT count(*) AS count FROM rebuilt_panorama_draw');count=cur.fetchone()['count']
        cur.execute('TRUNCATE public.panorama_coverage_draw,public.panorama_coverage_dirty')
        cur.execute('INSERT INTO public.panorama_coverage_draw SELECT * FROM rebuilt_panorama_draw')
        cur.execute('UPDATE public.panorama_catalog_totals SET version=version+1 WHERE id')
    lease.progress(100,'Покрытие перестроено',record=True)
    return {'chunks':count}
