"""Incremental spatial summaries: map work depends on viewport cells, not catalog size."""
import math
from flask import abort,request,jsonify

LEVELS=(0,4,8,12,16)
MAX_MARKERS=1000


def initialize(cur):
    cur.execute("SELECT to_regclass('public.panorama_catalog_totals') AS name")
    row=cur.fetchone();fresh=(row['name'] if isinstance(row,dict) else row[0]) is None
    cur.execute('''CREATE TABLE IF NOT EXISTS public.panorama_catalog_totals (
        id BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK(id),active BIGINT NOT NULL,trash BIGINT NOT NULL)''')
    cur.execute('ALTER TABLE public.panorama_catalog_totals ADD COLUMN IF NOT EXISTS version BIGINT NOT NULL DEFAULT 0')
    cur.execute('''CREATE TABLE IF NOT EXISTS public.panorama_spatial_cells (
        level SMALLINT NOT NULL,x INTEGER NOT NULL,y INTEGER NOT NULL,n BIGINT NOT NULL,
        sx DOUBLE PRECISION NOT NULL,sy DOUBLE PRECISION NOT NULL,PRIMARY KEY(level,x,y))''')
    if fresh:
        cur.execute('''INSERT INTO public.panorama_catalog_totals(id,active,trash) SELECT TRUE,
            count(*) FILTER(WHERE deleted_at IS NULL),count(*) FILTER(WHERE deleted_at IS NOT NULL)
            FROM public.photos_4326''')
        cur.execute('''INSERT INTO public.panorama_spatial_cells
            SELECT level,floor(ST_X(geom)/(360.0/power(2,level+3)))::int,
            floor(ST_Y(geom)/(360.0/power(2,level+3)))::int,count(*),sum(ST_X(geom)),sum(ST_Y(geom))
            FROM public.photos_4326 CROSS JOIN unnest(ARRAY[0,4,8,12,16]) level
            WHERE deleted_at IS NULL AND geom IS NOT NULL GROUP BY 1,2,3''')
    cur.execute('''CREATE OR REPLACE FUNCTION public.panorama_index_change() RETURNS trigger
        LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
        DECLARE old_active int:=0;new_active int:=0;old_trash int:=0;new_trash int:=0;
            lvl int;size float8;px float8;py float8;cx int;cy int;
        BEGIN
          IF TG_OP<>'INSERT' THEN
            IF OLD.deleted_at IS NULL THEN old_active:=1;ELSE old_trash:=1;END IF;
          END IF;
          IF TG_OP<>'DELETE' THEN
            IF NEW.deleted_at IS NULL THEN new_active:=1;ELSE new_trash:=1;END IF;
          END IF;
          UPDATE public.panorama_catalog_totals SET active=active+new_active-old_active,trash=trash+new_trash-old_trash,version=version+1 WHERE id;
          FOREACH lvl IN ARRAY ARRAY[0,4,8,12,16] LOOP
            size:=360.0/power(2,lvl+3);
            IF old_active=1 AND OLD.geom IS NOT NULL THEN
              px:=ST_X(OLD.geom);py:=ST_Y(OLD.geom);cx:=floor(px/size)::int;cy:=floor(py/size)::int;
              UPDATE public.panorama_spatial_cells SET n=n-1,sx=sx-px,sy=sy-py WHERE level=lvl AND x=cx AND y=cy;
              DELETE FROM public.panorama_spatial_cells WHERE level=lvl AND x=cx AND y=cy AND n=0;
            END IF;
            IF new_active=1 AND NEW.geom IS NOT NULL THEN
              px:=ST_X(NEW.geom);py:=ST_Y(NEW.geom);cx:=floor(px/size)::int;cy:=floor(py/size)::int;
              INSERT INTO public.panorama_spatial_cells VALUES(lvl,cx,cy,1,px,py)
                ON CONFLICT(level,x,y) DO UPDATE SET n=panorama_spatial_cells.n+1,sx=panorama_spatial_cells.sx+px,sy=panorama_spatial_cells.sy+py;
            END IF;
          END LOOP;
          RETURN NULL;
        END $$''')
    cur.execute('''CREATE OR REPLACE TRIGGER panorama_index_change AFTER INSERT OR DELETE OR UPDATE OF geom,deleted_at
        ON public.photos_4326 FOR EACH ROW EXECUTE FUNCTION public.panorama_index_change()''')
    cur.execute('CREATE INDEX IF NOT EXISTS photos_active_id_idx ON public.photos_4326(id DESC) WHERE deleted_at IS NULL')
    cur.execute('CREATE INDEX IF NOT EXISTS photos_active_geom_idx ON public.photos_4326 USING gist(geom) WHERE deleted_at IS NULL')


def totals(cur):
    cur.execute('SELECT active AS active_total,trash AS trash_total FROM public.panorama_catalog_totals WHERE id')
    return dict(cur.fetchone())


def viewport(allow_world=False):
    if allow_world and not any(k in request.args for k in ('west','south','east','north')):return -180,-85,180,85,0
    try:
        west,south,east,north=[float(request.args[k]) for k in ('west','south','east','north')]
        zoom=min(23,max(0,int(request.args.get('zoom',5))))
        if not all(math.isfinite(v) for v in (west,south,east,north)):raise ValueError()
    except (ValueError,KeyError):abort(400,description='Укажите видимую область карты.')
    west=max(-180,min(180,west));east=max(-180,min(180,east));south=max(-90,min(90,south));north=max(-90,min(90,north))
    if west>=east or south>=north:abort(400)
    return west,south,east,north,zoom


def markers(db,where='deleted_at IS NULL',values=None,allow_world=False):
    west,south,east,north,zoom=viewport(allow_world);values=list(values or [])
    # Bounds, rather than client zoom alone, bound the number of cells returned.
    level=next((z for z in reversed(LEVELS) if (east-west)/(360/2**(z+3))<=32 and (north-south)/(360/2**(z+3))<=24),0)
    summary=where=='deleted_at IS NULL' and not values
    with db.cursor() as cur:
        cur.execute('SET LOCAL statement_timeout=5000')
        if zoom>=18 or request.args.get('points')=='1':
            cur.execute('WITH visible AS MATERIALIZED (SELECT id,geom FROM public.photos_4326 WHERE '+where+
                ' AND geom && ST_MakeEnvelope(%s,%s,%s,%s,4326) LIMIT %s) '
                'SELECT id,ST_Y(geom) AS lat,ST_X(geom) AS lng,1 AS count FROM visible ORDER BY id DESC',values+[west,south,east,north,MAX_MARKERS+1])
            rows=cur.fetchall()
            if len(rows)<=MAX_MARKERS or zoom>=23 or request.args.get('points')=='1':return jsonify(rows[:MAX_MARKERS])
        if summary:
            size=360/2**(level+3)
            cur.execute("""SELECT concat(level,':',x,':',y) AS id,sy/n AS lat,sx/n AS lng,n AS count,TRUE AS cluster
                FROM public.panorama_spatial_cells WHERE level=%s AND x BETWEEN %s AND %s AND y BETWEEN %s AND %s
                ORDER BY x,y LIMIT %s""",(level,math.floor(west/size),math.floor(east/size),math.floor(south/size),math.floor(north/size),MAX_MARKERS))
        else:
            # Filtered catalogs keep exact membership; visible-area query uses GiST.
            grid=max((east-west)/32,(north-south)/24,1e-7)
            cur.execute('''SELECT min(id) AS id,avg(ST_Y(geom)) AS lat,avg(ST_X(geom)) AS lng,count(*) AS count,
                count(*)>1 AS cluster FROM public.photos_4326 WHERE '''+where+'''
                AND geom && ST_MakeEnvelope(%s,%s,%s,%s,4326) GROUP BY ST_SnapToGrid(geom,%s) LIMIT %s''',values+[west,south,east,north,grid,MAX_MARKERS])
        return jsonify(cur.fetchall())
