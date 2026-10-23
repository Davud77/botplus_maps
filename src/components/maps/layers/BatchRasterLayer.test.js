import L from 'leaflet';
import {waitFor} from '@testing-library/react';
import {BatchRasterLayer} from './BatchRasterLayer';
const coords=(x,y)=>Object.assign(L.point(x,y),{z:17});
let flush;
beforeEach(()=>{
 jest.spyOn(window,'requestAnimationFrame').mockImplementation(callback=>{flush=callback;return 1;});
 URL.createObjectURL=jest.fn(()=>`blob:${Math.random()}`);URL.revokeObjectURL=jest.fn();
 global.fetch=jest.fn();
});
afterEach(()=>jest.restoreAllMocks());
const layer=()=>new BatchRasterLayer('/api/orthophotos/1/tiles/{z}/{x}/{y}@2x.webp',{tileSize:512,zoomOffset:-1});
const frame=(x,y)=>JSON.stringify({x,y,data:btoa('RIFFtestWEBPimage')})+'\n';
test('coalesces visible tiles, applies URL zoom offset and handles wrapped duplicates',async()=>{
 fetch.mockResolvedValue({ok:true,body:null,text:async()=>frame(2,3)+frame(1,3)});
 const grid=layer(),done1=jest.fn(),done2=jest.fn(),done3=jest.fn();
 const a=grid.createTile(coords(1,3),done1),b=grid.createTile(coords(2,3),done2),copy=grid.createTile(coords(1,3),done3);
 flush();await waitFor(()=>expect(a.src).toMatch(/^blob:/));
 expect(fetch).toHaveBeenCalledTimes(1);
 const url=new URL(fetch.mock.calls[0][0],'http://localhost');expect(url.pathname).toBe('/api/orthophotos/1/tiles/batch');expect(url.searchParams.get('z')).toBe('16');
 expect(fetch.mock.calls[0][1].credentials).toBe('include');expect(done1).not.toHaveBeenCalled();
 [a,b,copy].forEach(tile=>tile.dispatchEvent(new Event('load')));
 expect(done1).toHaveBeenCalledWith(undefined,a);expect(done2).toHaveBeenCalledWith(undefined,b);expect(done3).toHaveBeenCalledWith(undefined,copy);
 expect(URL.revokeObjectURL).toHaveBeenCalledTimes(3);
});
test('cancelled queued tiles are not requested',()=>{
 const grid=layer(),done=jest.fn(),tile=grid.createTile(coords(1,3),done);
 grid.fire('tileunload',{tile});flush();expect(fetch).not.toHaveBeenCalled();expect(done).not.toHaveBeenCalled();
});
test('reports failed and missing frames so the loading indicator cannot hang',async()=>{
 fetch.mockResolvedValue({ok:true,body:null,text:async()=>JSON.stringify({x:1,y:3,error:409})+'\n'});
 const grid=layer(),a=jest.fn(),b=jest.fn();grid.createTile(coords(1,3),a);grid.createTile(coords(2,3),b);flush();
 await waitFor(()=>expect(b).toHaveBeenCalled());expect(a.mock.calls[0][0]).toBeInstanceOf(Error);expect(b.mock.calls[0][0]).toBeInstanceOf(Error);
});
test('decodes split streamed lines and displays the first tile before the stream ends',async()=>{
 const {TextEncoder,TextDecoder}=require('util');global.TextDecoder=TextDecoder;
 const encoder=new TextEncoder();let release;const tail=new Promise(resolve=>{release=resolve;});
 const first=frame(1,3);const reads=[Promise.resolve({value:encoder.encode(first.slice(0,7)),done:false}),Promise.resolve({value:encoder.encode(first.slice(7)),done:false}),tail,Promise.resolve({done:true})];
 const reader={read:jest.fn(()=>reads.shift()),cancel:jest.fn(async()=>{}),releaseLock:jest.fn()};
 fetch.mockResolvedValue({ok:true,body:{getReader:()=>reader}});
 const grid=layer(),a=grid.createTile(coords(1,3),jest.fn()),b=grid.createTile(coords(2,3),jest.fn());flush();
 await waitFor(()=>expect(a.src).toMatch(/^blob:/));expect(b.getAttribute('src')).toBeNull();
 release({value:encoder.encode(frame(2,3)),done:false});await waitFor(()=>expect(b.src).toMatch(/^blob:/));
 expect(reader.releaseLock).toHaveBeenCalled();
});
test('invalid image encoding completes tiles with errors instead of hanging',async()=>{
 fetch.mockResolvedValue({ok:true,body:null,text:async()=>JSON.stringify({x:1,y:3,data:'!invalid!'})+'\n'});
 const grid=layer(),done=jest.fn();grid.createTile(coords(1,3),done);flush();
 await waitFor(()=>expect(done).toHaveBeenCalled());expect(done.mock.calls[0][0]).toBeInstanceOf(Error);
});
