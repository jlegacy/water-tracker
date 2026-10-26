"""Browser QA: pinch/zoom snaps range (5->50->5), syncs UI/storage/server; programmatic fits do not loop.
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
  await pg.goto(URL); await pg.wait_for_timeout(800)
  await pg.fill('#startName',f'QA PZ {n}'); await pg.evaluate("()=>startApp()"); await pg.wait_for_timeout(2500)
  far=await F(f'{n}-far30',lat+30*MI,lon).open(); await pg.wait_for_timeout(1200)
  st=lambda: pg.evaluate("()=>({r:myRange,z:map.getZoom(),fit:rangeZoomFor(myRange),sel:document.getElementById('rangeSel').value,ls:localStorage.getItem('trackerRange'),ids:Object.keys(positions).filter(k=>k!==me)})")
  s=await st(); ok(n,'start 5 mi, far rider hidden',s['r']==5 and f'{n}-far30' not in s['ids'],s)
  # programmatic setView/fitBounds without user input: no snap, no loop
  await pg.evaluate("()=>map.setView(myLatLng, map.getZoom()-3, {animate:false})"); await pg.wait_for_timeout(500)
  s=await st(); ok(n,'programmatic zoom does not change range',s['r']==5,s)
  await pg.evaluate("()=>fitRangeCircle()"); await pg.wait_for_timeout(300)
  # simulated pinch-out well past the 50 mi zoom (wide out)
  await pg.evaluate("()=>{markUserZoom(); map.setZoom(rangeZoomFor(50)-1.5,{animate:false})}"); await pg.wait_for_timeout(1500)
  s=await st(); ok(n,'pinch out snaps 5 -> 50, dropdown+storage synced, refit',s['r']==50 and s['sel']=='50' and s['ls']=='50' and abs(s['z']-s['fit'])<0.01,s)
  ok(n,'server got range 50: far rider at 30 mi now shown',f'{n}-far30' in s['ids'],s)
  # pinch in near the 15 mi zoom
  await pg.evaluate("()=>{markUserZoom(); map.setZoom(rangeZoomFor(15)-0.1,{animate:false})}"); await pg.wait_for_timeout(1500)
  s=await st(); ok(n,'pinch in snaps 50 -> 15',s['r']==15 and abs(s['z']-s['fit'])<0.01,s)
  # pinch in hard past every option (clamped at maxZoom) -> 1 mi
  await pg.evaluate("()=>{markUserZoom(); map.setZoom(map.getMaxZoom(),{animate:false})}"); await pg.wait_for_timeout(1500)
  s=await st(); ok(n,'pinch to max zoom sets 1 mi',s['r']==1,s)
  ok(n,'max zoom raised to 21',await pg.evaluate("()=>map.getMaxZoom()")==21)
  # from 5 mi, deep pinch past 1 mi fit: range 1, NO snap-back
  await pg.evaluate("()=>setRange(5)"); await pg.wait_for_timeout(800)
  await pg.evaluate("()=>{markUserZoom(); map.setZoom(rangeZoomFor(1)+2.5,{animate:false})}"); await pg.wait_for_timeout(1500)
  want=await pg.evaluate("()=>rangeZoomFor(1)+2.5")
  s=await st(); ok(n,'deep pinch: range 1, synced, zoom kept (no snap-back)',s['r']==1 and s['sel']=='1' and s['ls']=='1' and abs(s['z']-want)<0.01,s)
  await sos_pos(pg)  # position update must not refit
  s2=await st(); ok(n,'position update/resize does not re-zoom',abs(s2['z']-want)<0.01,s2)
  await pg.evaluate("()=>{markUserZoom(); map.setZoom(map.getZoom()+1,{animate:false})}"); await pg.wait_for_timeout(1200)
  s=await st(); ok(n,'deeper pinch at 1 mi stays put',abs(s['z']-want-1)<0.01 and s['r']==1,s)
  # zoom back out above 1 mi level snaps
  await pg.evaluate("()=>{markUserZoom(); map.setZoom(rangeZoomFor(10),{animate:false})}"); await pg.wait_for_timeout(1500)
  s=await st(); ok(n,'zoom back out snaps to 10',s['r']==10 and abs(s['z']-s['fit'])<0.01,s)
  # small nudge -> snaps back to same option
  await pg.evaluate("()=>{setRange(5)}"); await pg.wait_for_timeout(800)
  await pg.evaluate("()=>{markUserZoom(); map.setZoom(map.getZoom()+0.3,{animate:false})}"); await pg.wait_for_timeout(1200)
  s=await st(); ok(n,'small nudge snaps back to 5 mi fit',s['r']==5 and abs(s['z']-s['fit'])<0.01,s)
  ok(n,'far rider hidden again at 5 mi',f'{n}-far30' not in s['ids'],s)
  if n=='chromium':  # real wheel input
    box=await pg.locator('#map').bounding_box()
    await pg.mouse.move(box['x']+box['width']/2,box['y']+box['height']/2)
    for _ in range(8): await pg.mouse.wheel(0,300); await pg.wait_for_timeout(150)
    await pg.wait_for_timeout(1500); s=await st(); ok(n,'real wheel zoom-out raises range',s['r']>5 and abs(s['z']-s['fit'])<0.01,s)
  await pg.screenshot(path=f'/workspace/pinch_{n}.png')
  ok(n,'no page errors',not errs,errs)
  await pg.evaluate("()=>{try{leaveApp&&leaveApp()}catch(e){}}"); await far.close(); await b.close()
async def main():
  async with async_playwright() as p:
    for n in BROWSERS: await run(p,n,-78.6)
  f=[k for k,v in R if not v]; print('FAILS',f); sys.exit(1 if f else 0)
asyncio.run(main())
