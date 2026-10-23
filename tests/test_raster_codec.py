from io import BytesIO
from pathlib import Path
import struct
import sys
import unittest
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
from raster_codec import decode_npy


def npy(image):
    shape=(len(image.getbands()),image.height,image.width)
    text=repr({'descr':'|u1','fortran_order':False,'shape':shape})
    header=(text+' '*((64-(10+len(text)+1)%64)%64)+'\n').encode('ascii')
    return b'\x93NUMPY\x01\x00'+struct.pack('<H',len(header))+header+b''.join(b.tobytes() for b in image.split())

class RasterCodecTests(unittest.TestCase):
    def test_planar_rgba_and_grayscale_keep_every_pixel_and_mask(self):
        image=Image.new('RGBA',(512,512),(12,47,98,255));image.putpixel((10,20),(240,1,44,0))
        self.assertEqual(decode_npy(npy(image),512).tobytes(),image.tobytes())
        gray=Image.new('LA',(256,256),(63,120));self.assertEqual(decode_npy(npy(gray),256).getpixel((0,0)),(63,63,63,120))
    def test_rejects_pickle_dtype_header_truncation_and_wrong_size(self):
        data=npy(Image.new('RGBA',(512,512)))
        for broken in [data[:-1],data[:20],data.replace(b'|u1',b'|O8'),data.replace(b'False',b'True '),b'bad']:
            with self.assertRaises(ValueError):decode_npy(broken,512)
        with self.assertRaises(ValueError):decode_npy(data,256)
