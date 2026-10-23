"""Bounded, progressive tile transport. Authentication is performed by the route.

Each NDJSON record is an independently usable WebP. A slow/missing tile does not
hold the first image. Source checks and NAS cache remain in OrthoService.
"""
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from flask import Response, abort, request
from werkzeug.exceptions import HTTPException

_executor = ThreadPoolExecutor(max_workers=6, thread_name_prefix='raster')


def tile_stream(service, ortho_id):
    try:
        z = int(request.args['z'])
        pairs = request.args['tiles'].split(';')
        if not 1 <= len(pairs) <= 24 or not 0 <= z <= 24:raise ValueError()
        tiles = []
        for pair in pairs:
            x,y = map(int,pair.split(','))
            if not 0 <= x < 2**z or not 0 <= y < 2**z:raise ValueError()
            if (x,y) not in tiles:tiles.append((x,y))
    except (ValueError,KeyError):abort(400,description='Некорректный набор тайлов.')

    def render(x,y):
        metrics = {}
        try:
            value = service.proxy_tile(ortho_id,z,x,y,scale=2,image_format='webp',metrics=metrics)
            if not value:return {'x':x,'y':y,'error':502}
            return {'x':x,'y':y,'data':base64.b64encode(value).decode('ascii'),**metrics}
        except HTTPException as error:return {'x':x,'y':y,'error':error.code}
        except Exception:return {'x':x,'y':y,'error':502}

    def generate():
        futures = [_executor.submit(render,x,y) for x,y in tiles]
        try:
            for future in as_completed(futures):
                yield json.dumps(future.result(),separators=(',',':'))+'\n'
        finally:
            # Running reads may finish and populate cache; queued work is cancelled.
            for future in futures:future.cancel()

    return Response(generate(),mimetype='application/x-ndjson',headers={
        'Cache-Control':'no-store','X-Accel-Buffering':'no','X-Content-Type-Options':'nosniff'})
