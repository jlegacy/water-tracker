"""Browser QA: fixed 50 mi: riders at 30 mi show outside the 5 mi ring (normal + SOS); 55 mi hidden; cleared SOS stays shown.
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
async def run(p,n,lon):
  lat=35.807
  if n=='webkit':
    dev=dict(p.devices['iPhone 15']); dev.pop('default_browser_type',None); b=await p.webkit.launch(); c=await b.new_context(**dev)
  else: b=await p.chromium.launch(); c=await b.new_context(viewport={'width':393,'height':852})
  await c.route('**/*onrender.com*/**',lambda r:r.abort()); await c.add_init_script(init(lat,lon))
  pg=await c.new_page(); errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)))
  await pg.goto(URL); await pg.wait_for_timeout(800)
  ok(n,'join screen has no range control',await pg.evaluate("()=>!document.getElementById('startRange')&&!document.getElementById('rangeNote')"))
  await pg.fill('#startName',f'QA SOS {n}'); await pg.evaluate("()=>startApp()"); await pg.wait_for_timeout(2500)
  ok(n,'view ring 5 mi, server range 50',await pg.evaluate("()=>[myViewR,myRange]")==[5,50])
  norm=await F(f'{n}-norm30',lat+30*MI,lon).open(); sos=await F(f'{n}-sos30',lat-30*MI,lon).open(); far=await F(f'{n}-far55',lat+55*MI,lon).open(); await pg.wait_for_timeout(1500)
  ids=await pg.evaluate("()=>Object.keys(positions).filter(k=>k!==me)"); ok(n,'30 mi riders shown outside ring, 55 mi hidden',sorted(ids)==sorted([f'{n}-norm30',f'{n}-sos30']),ids)
  await sos.send(type='sos',on=True); await pg.wait_for_timeout(1500)
  st=await pg.evaluate("""()=>{const id=Object.keys(positions).filter(k=>k!==me&&/sos/.test(k));const p=positions[id[0]]||{};
    const opts=[...document.getElementById('riderList').options].map(o=>[o.textContent,o.dataset.st]);
    const bar=document.getElementById('sosBar');const inMap=id.length&&map.hasLayer(riders[id[0]]);
    const d=id.length?map.distance(L.latLng(p.lat,p.lon),L.latLng(myLatLng))/1609.344:0;
    return {id,sos:!!p.sos,opts,bar:bar.style.display!=='none'?bar.textContent:'',inMap,d}}""")
  ok(n,'SOS rider at 30 mi shown (outside 5 mi circle)',st['id']==[f'{n}-sos30'] and st['sos'] and st['inMap'] and st['d']>25,st)
  ok(n,'normal rider at 30 mi also shown',await pg.evaluate(f"()=>!!positions['{n}-norm30']"),st)
  ok(n,'riders drop-down lists SOS rider as SOS',any(f'{n}-sos30' in t and s=='s' for t,s in st['opts']),st['opts'])
  ok(n,'SOS bar shown',f'{n}-sos30' in st['bar'],st['bar'])
  await pg.screenshot(path=f'/workspace/sos_range_{n}.png')
  await sos.send(type='pos',lat=lat-31*MI,lon=lon,ts=time.time()*1000); await pg.wait_for_timeout(1000)
  la=await pg.evaluate(f"()=>positions['{n}-sos30']&&positions['{n}-sos30'].lat"); ok(n,'SOS position update arrives',la and abs(la-(lat-31*MI))<1e-6,la)
  await sos.send(type='sos',on=False); await pg.wait_for_timeout(1500)
  st=await pg.evaluate("()=>[Object.keys(positions).filter(k=>k!==me),[...document.getElementById('riderList').options].map(o=>o.textContent),document.getElementById('sosBar').style.display]")
  ok(n,'SOS cleared -> bar cleared, rider still shown (within 50)',f'{n}-sos30' in st[0] and st[2]=='none',st)
  await norm.close(); await sos.close(); await far.close()
  await pg.evaluate("()=>{try{ws.send(JSON.stringify({type:'leave'}))}catch(e){}}")
  ok(n,'no page errors',not errs,errs); await c.close(); await b.close()
async def main():
  async with async_playwright() as p:
    for i,n in enumerate(BROWSERS): await run(p,n,-77.378+i*3)
  f=[k for k,v in R if not v]; print('ALL PASS' if not f else 'FAILED: '+', '.join(f)); sys.exit(1 if f else 0)
asyncio.run(main())
