"""Decode TiTiler's planar byte array without pickle or a NumPy dependency."""
import ast
import struct
from PIL import Image


def decode_npy(value,size):
    if len(value)<10 or value[:6]!=b'\x93NUMPY':raise ValueError('Invalid raster array')
    version=tuple(value[6:8])
    if version==(1,0):offset=10;length=struct.unpack('<H',value[8:10])[0]
    elif version==(2,0) and len(value)>=12:offset=12;length=struct.unpack('<I',value[8:12])[0]
    else:raise ValueError('Unsupported array version')
    if length>1024 or len(value)<offset+length:raise ValueError('Invalid array header')
    try:header=ast.literal_eval(value[offset:offset+length].decode('ascii').strip())
    except (ValueError,SyntaxError,UnicodeError,TypeError):raise ValueError('Invalid array header') from None
    if not isinstance(header,dict) or set(header)!={'descr','fortran_order','shape'} or type(header['descr']) is not str or header['descr'] not in {'|u1','<u1','>u1'} or header['fortran_order'] is not False:raise ValueError('Only byte rasters are supported')
    shape=header['shape']
    if not isinstance(shape,tuple) or len(shape)!=3 or any(type(n) is not int for n in shape) or not 1<=shape[0]<=4 or shape[1:]!=(size,size):raise ValueError('Invalid raster dimensions')
    pixels=value[offset+length:];plane=size*size
    if len(pixels)!=plane*shape[0]:raise ValueError('Incomplete raster array')
    bands=[Image.frombytes('L',(size,size),pixels[i*plane:(i+1)*plane]) for i in range(shape[0])]
    return Image.merge({1:'L',2:'LA',3:'RGB',4:'RGBA'}[len(bands)],bands).convert('RGBA') if len(bands)>1 else bands[0].convert('RGBA')
