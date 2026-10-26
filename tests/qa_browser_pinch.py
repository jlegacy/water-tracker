"""Browser QA: continuous pinch radius (display, circle, server clamp 1-50), no snapping, syncs UI/storage/server; programmatic fits do not loop.
Was: SOS reaches a 5 mi receiver from 30 mi (max range 50); a normal rider at 30 mi stays hidden; cleared SOS hides again.
Usage: python qa_browser_sos_range.py http://172.30.0.2:8777/ [chromium|webkit]"""
import asyncio, sys, json, time, websockets
from playwright.async_api import async_playwright
URL=sys.argv[1]; WS=URL.replace('http','ws')+'ws'; BROWSERS=sys.argv[2:] or ['chromium','webkit']
MI=1/69.05
R=[]
def ok(n,k,v,d=''): R.append((n+' '+k,bool(v))); print(n,k,'PASS' if v else 'FAIL',d if not v else '')
def init(lat,lon): return """(()=>{const mk=()=>({coords:{latitude:%f,longitude:%f,accuracy:5,heading:null,speed:null},timestamp:Date.now()});
const g={getCurrentPosition(ok){setTimeout(()=>ok(mk()),300)},watchPosition(ok){setTimeout(()=>ok(mk()),300);setInterval(()=>ok(mk()),3000);return 1},clearWatch(){}};
Object.defineProperty(navigator,'geolocation',{get:()=>g});})()"""%(lat,lon)
class F:
  def __init__(s,rid,lat,lon): s.id,s.lat,s.lon=rid,lat,lon
  async def open(s):
    s.ws=await websockets.connect(WS); await s.ws.send(json.dumps(dict(type='join',id=s.id,name=s.id,range=50)))
    await s.ws.send(json.dumps(dict(type='pos',lat=s.lat,lon=s.lon,ts=time.time()*1000))); return s
  async def send(s,**m): await s.ws.send(json.dumps(m))
  async def close(s): await s.send(type='leave'); await s.ws.close()
async def sos_pos(pg):
  await pg.evaluate("()=>{window.dispatchEvent(new Event('resize')); drawRangeCircle();}"); await pg.wait_for_timeout(3800)
async def run(p,n,lon):
  lat=35.807
  if n=='webkit':
    dev=dict(p.devices['iPhone 15']); dev.pop('default_browser_type',None); b=await p.webkit.launch(); c=await b.new_context(**dev)
  else: b=await p.chromium.launch(); c=await b.new_context(viewport={'width':393,'height':852})
  await c.route('**/*onrender.com*/**',lambda r:r.abort()); await c.add_init_script(init(lat,lon))
  pg=await c.new_page(); errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)))
  await c.add_init_script("try{localStorage.setItem('trackerRange','40')}catch(e){}")
  await pg.goto(URL); await pg.wait_for_timeout(800)
  await pg.fill('#startName',f'QA PZ {n}'); await pg.evaluate("()=>startApp()"); await pg.wait_for_timeout(2500)
  far=await F(f'{n}-far30',lat+30*MI,lon).open(); far7=await F(f'{n}-far7',lat-7*MI,lon).open(); await pg.wait_for_timeout(1200)
  st=lambda: pg.evaluate("()=>({r:myRange,v:myViewR,z:map.getZoom(),txt:document.getElementById('rangeVal').textContent,circ:rangeCircle&&rangeCircle.getRadius()/1609.344,calc:radiusForZoom(map.getZoom()),ids:Object.keys(positions).filter(k=>k!==me)})")
  ui=await pg.evaluate("()=>({sel:document.getElementById('rangeSel').tagName==='SELECT'||!!document.querySelector('#bar .cpick.rng select'),menu:document.querySelector('#bar .cpick.rng .cmenu'),opts:document.querySelectorAll('#bar .cpick.rng [role=option]').length,join:!!document.getElementById('startRange')})")
  ok(n,'range display is read-only (no select/menu/options), none on join',not ui['sel'] and not ui['menu'] and ui['opts']==0 and not ui['join'],ui)
  s=await st(); ok(n,'session starts at 5 mi fitted to width (ignores stored range)',s['r']==5 and s['txt']=='5.0 mi' and abs(s['calc']-5)<0.05,s)
  # programmatic zoom: no change
  await pg.evaluate("()=>map.setView(myLatLng, map.getZoom()-3, {animate:false})"); await pg.wait_for_timeout(500)
  s=await st(); ok(n,'programmatic zoom does not change range',s['r']==5 and s['txt']=='5.0 mi',s)
  await pg.evaluate("()=>fitRangeCircle()"); await pg.wait_for_timeout(300)
  # pinch out to ~7.3 mi: continuous, no snap
  await pg.evaluate("()=>{markUserZoom(); map.setZoom(rangeZoomFor(7.3),{animate:false})}"); await pg.wait_for_timeout(1500)
  s=await st(); ok(n,'pinch -> 7.3 mi shown, circle+server follow, zoom kept',s['txt']=='7.3 mi' and abs(s['r']-7.3)<0.05 and abs(s['circ']-7.3)<0.05 and abs(s['calc']-7.3)<0.05,s)
  ok(n,'rider at 7 mi now shown, 30 mi not',f'{n}-far7' in s['ids'] and f'{n}-far30' not in s['ids'],s)
  await pg.evaluate("()=>{markUserZoom(); map.setZoom(rangeZoomFor(31.6),{animate:false})}"); await pg.wait_for_timeout(1500)
  s=await st(); ok(n,'pinch -> 32 mi (whole number >=10), 30 mi rider shown',s['txt']=='32 mi' and abs(s['r']-31.6)<0.1 and f'{n}-far30' in s['ids'],s)
  # deep pinch below 1 mi: true value shown, server stays 1, no snap-back
  await pg.evaluate("()=>{markUserZoom(); map.setZoom(rangeZoomFor(0.4),{animate:false})}"); await pg.wait_for_timeout(1500)
  want=await pg.evaluate("()=>map.getZoom()")
  s=await st(); ok(n,'deep pinch: shows 0.4 mi, server range 1, circle 0.4',s['txt']=='0.4 mi' and s['r']==1 and abs(s['circ']-0.4)<0.02,s)
  await pg.evaluate("()=>{window.dispatchEvent(new Event('resize')); drawRangeCircle();}"); await pg.wait_for_timeout(3800)
  s=await st(); ok(n,'no snap-back after position update/resize',abs(s['z']-want)<0.01,s)
  ok(n,'max zoom 21',await pg.evaluate("()=>map.getMaxZoom()")==21)
  # zoom far out beyond 50: display true, server clamped 50
  await pg.evaluate("()=>{markUserZoom(); map.setZoom(rangeZoomFor(80),{animate:false})}"); await pg.wait_for_timeout(1500)
  s=await st(); ok(n,'zoom-out locked at 50: display 50 mi, server 50',s['txt']=='50 mi' and s['r']==50 and abs(s['z']-pg_minz)<0.01 if (pg_minz:=await pg.evaluate("()=>map.getMinZoom()")) else False,s)
  mz=await pg.evaluate("()=>({mz:map.getMinZoom(),want:rangeZoomFor(MAX_RANGE_MI)})"); ok(n,'minZoom == rangeZoomFor(50)',abs(mz['mz']-mz['want'])<1e-3,mz)
  fz=await pg.evaluate("()=>{map.fitBounds([[myLatLng[0]-5,myLatLng[1]-5],[myLatLng[0]+5,myLatLng[1]+5]],{animate:false});return map.getZoom()-map.getMinZoom()}"); ok(n,'fitBounds respects 50 mi lock',fz>-0.01,fz)
  vz=await pg.evaluate("()=>{map.setView(myLatLng,3,{animate:false});return map.getZoom()-map.getMinZoom()}"); ok(n,'setView respects 50 mi lock',fz>-0.01 and vz>-0.01,vz)
  await pg.set_viewport_size({'width':800,'height':500}); await pg.wait_for_timeout(800)
  r2=await pg.evaluate("()=>({mz:map.getMinZoom(),want:rangeZoomFor(MAX_RANGE_MI)})"); ok(n,'minZoom recomputed on resize',abs(r2['mz']-r2['want'])<1e-3 and abs(r2['mz']-mz['mz'])>0.1,r2)
  # live display during pinch (zoom event before zoomend)
  live=await pg.evaluate("()=>new Promise(r=>{markUserZoom();map.once('zoom',()=>r(document.getElementById('rangeVal').textContent));map.setZoom(rangeZoomFor(12),{animate:false})})")
  ok(n,'display updates live on zoom event',live=='12 mi',live)
  await pg.evaluate("()=>setRange(5)"); await pg.wait_for_timeout(1200)
  s=await st(); ok(n,'setRange(5) refits, 30/7 mi riders hidden',s['txt']=='5.0 mi' and abs(s['calc']-5)<0.05 and f'{n}-far30' not in s['ids'] and f'{n}-far7' not in s['ids'],s)
  if n=='chromium':
    box=await pg.locator('#map').bounding_box()
    await pg.mouse.move(box['x']+box['width']/2,box['y']+box['height']/2)
    for _ in range(4): await pg.mouse.wheel(0,200); await pg.wait_for_timeout(150)
    await pg.wait_for_timeout(1500); s=await st(); ok(n,'real wheel zoom-out raises radius continuously',s['v']>5 and abs(s['calc']-s['v'])<0.05,s)
  await pg.screenshot(path=f'/workspace/pinch_{n}.png')
  ok(n,'no page errors',not errs,errs)
  await pg.evaluate("()=>{try{leaveApp&&leaveApp()}catch(e){}}"); await far.close(); await far7.close(); await b.close()
async def main():
  async with async_playwright() as p:
    for n in BROWSERS: await run(p,n,-78.6)
  f=[k for k,v in R if not v]; print('FAILS',f); sys.exit(1 if f else 0)
asyncio.run(main())
