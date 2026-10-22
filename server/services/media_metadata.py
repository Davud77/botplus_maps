"""Read image headers only; never interpret an ordinary photo as a sphere."""
import re
from pathlib import Path
from PIL import Image


def media_kind(width, height, xmp=b''):
    # EquirectGeometry requires a complete 2:1 sphere. Cropped GPano images need
    # a dedicated preparation step; displaying them as photos preserves shape.
    if width != height * 2:
        return 'photo'
    if isinstance(xmp, bytes):
        xmp = xmp.decode('utf-8', errors='replace')
    declared = bool(re.search(r'GPano:ProjectionType\s*(?:=\s*[\"\']equirectangular[\"\']|>\s*equirectangular\s*<)', xmp or '', re.I))
    # Old exports may omit XMP. A large complete 2:1 image is a heuristic;
    # the viewer also lets the user display it as a flat photo.
    return 'panorama' if declared or width >= 1024 else 'photo'


def read_media_metadata(path):
    with Image.open(path) as image:
        return {'width': image.width, 'height': image.height,
                'media_type': media_kind(image.width, image.height, image.info.get('xmp', b''))}


def display_name(key):
    return re.sub(r'^[a-f0-9]{32}_', '', Path(key).name)
