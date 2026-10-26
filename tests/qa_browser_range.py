"""Browser QA for the viewing-range drop-down. Usage: python qa_browser_range.py http://127.0.0.2:8811/ [chromium|webkit]"""
import asyncio, sys, json, time, websockets
from playwright.async_api import async_playwright
URL=sys.argv[1]; WS=URL.replace('http','ws')+'ws'; BROWSERS=sys.argv[2:] or ['chromium','webkit']
LAT0,LON0=35.807,-77.378; MI=1/69.05
INIT="""(()=>{const mk=()=>({coords:{latitude:%f,longitude:%f,accuracy:5,heading:null,speed:null},timestamp:Date.now()});
const g={getCurrentPosition(ok){setTimeout(()=>ok(mk()),1500)},watchPosition(ok){setTimeout(()=>ok(mk()),1500);setInterval(()=>ok(mk()),4000);return 1},clearWatch(){}};
Object.defineProperty(navigator,'geolocation',{get:()=>g});
const S=WebSocket.prototype.send;WebSocket.prototype.send=function(d){try{(window.__out=window.__out||[]).push(JSON.parse(d))}catch(e){}return S.call(this,d)};})()"""%(LAT0,LON0)
R=[]
def ok(n,k,v,d=''): R.append((n+' '+k,bool(v))); print(n,k,'PASS' if v else 'FAIL',d if not v else '')
async def pick(pg,v):
  # Range is a custom picker (same component as the riders list): open it and tap the option
  await pg.click('#bar .cpick.rng .cbtn'); await pg.click(f"#bar .cpick.rng .cmenu div:text-is('{v} mi')")
class F:
  def __init__(s,rid): s.id=rid
  async def open(s,mi):
    s.ws=await websockets.connect(WS); await s.ws.send(json.dumps(dict(type='join',id=s.id,name=s.id)))
    await s.ws.send(json.dumps(dict(type='pos',lat=LAT0+mi*MI,lon=LON0,ts=time.time()*1000))); return s
  async def close(s): await s.ws.send(json.dumps({'type':'leave'})); await s.ws.close()
async def run(p,n):
  if n=='webkit':
    dev=dict(p.devices['iPhone 15']); dev.pop('default_browser_type',None); b=await p.webkit.launch(); c=await b.new_context(**dev)
  else: b=await p.chromium.launch(); c=await b.new_context()
  await c.route('**/*onrender.com*/**',lambda r:r.abort()); await c.add_init_script(INIT)
  pg=await c.new_page(); errs=[]; nav=[False]; navErrs=[]; pg.on('pageerror',lambda e:(navErrs if nav[0] else errs).append(str(e)))
  await pg.goto(URL); await pg.wait_for_timeout(1200)
  v=await pg.evaluate("()=>[document.getElementById('startRange')&&document.getElementById('startRange').value,!!document.getElementById('rangeSel'),[...document.getElementById('startRange').options].map(o=>o.value),document.getElementById('rangeNote').textContent]")
  ok(n,'join drop-down present, default 25',v[0]=='25' and v[1] and v[2]==['25','30','35','40','45','50'] and '25 miles' in v[3],v)
  await pg.click('#nameScreen .cpick.rng-start .cbtn'); await pg.click("#nameScreen .cpick.rng-start .cmenu div:text-is('35 mi')")
  v=await pg.evaluate("()=>[localStorage.getItem('trackerRange'),document.getElementById('rangeNote').textContent]")
  ok(n,'join pick persisted + note updates',v[0]=='35' and '35 miles' in v[1],v)
  fs=[await F(f'{n}-r{mi}').open(mi) for mi in (24,32,-48,52)]
  await pg.fill('#startName',f'QA {n}'); await pg.evaluate("()=>startApp()"); await pg.wait_for_timeout(3500)
  st=await pg.evaluate("()=>[document.getElementById('status').textContent,document.getElementById('rangeSel').value,(window.__out||[]).filter(m=>m.type==='join').map(m=>m.range)]")
  ok(n,'status + map select show 35, join sends range',st[0]=='Sharing — riders within 35 mi' and st[1]=='35' and st[2] and st[2][-1]==35,st)
  IDS="()=>Object.keys(positions).filter(k=>k!==me).sort()"
  ids=await pg.evaluate(IDS); ok(n,'35 mi list: 24, 32',ids==[f'{n}-r24',f'{n}-r32'],ids)
  vis=await pg.evaluate("()=>{const r=document.querySelector('#bar .cpick.rng').getBoundingClientRect();return r.width>0&&r.height>0}")
  ok(n,'map drop-down visible',vis)
  await pick(pg,'50'); await pg.wait_for_timeout(1200)
  ids=await pg.evaluate(IDS); st=await pg.evaluate("()=>[document.getElementById('status').textContent,localStorage.getItem('trackerRange'),(window.__out||[]).filter(m=>m.type==='join').length]")
  ok(n,'live switch to 50 adds 48 (not 52), no rejoin',ids==[f'{n}-r-48',f'{n}-r24',f'{n}-r32'] and st[0].endswith('50 mi') and st[1]=='50' and st[2]==1,[ids,st])
  lst=await pg.evaluate("()=>[...document.getElementById('riderList').options].map(o=>o.textContent)")
  ok(n,'rider drop-down lists 3 riders',len(lst)==4,lst)
  await pick(pg,'25'); await pg.wait_for_timeout(1200)
  ids=await pg.evaluate(IDS); ok(n,'live switch to 25 drops 32/48',ids==[f'{n}-r24'],ids)
  await pick(pg,'40'); await pg.wait_for_timeout(800)
  nav[0]=True; await pg.reload(); await pg.wait_for_timeout(1200); nav[0]=False
  v=await pg.evaluate("()=>[document.getElementById('startRange').value,document.getElementById('rangeSel').value,document.getElementById('rangeNote').textContent]")
  ok(n,'persists after reload (40)',v[0]=='40' and v[1]=='40' and '40 miles' in v[2],v)
  await pg.evaluate("()=>localStorage.setItem('trackerRange','99')"); nav[0]=True; await pg.reload(); await pg.wait_for_timeout(800); nav[0]=False
  v=await pg.evaluate("()=>document.getElementById('startRange').value"); ok(n,'bad stored value -> 25',v=='25',v)
  await pg.evaluate("()=>{try{navigator.sendBeacon&&0}catch(e){}}")
  for f in fs: await f.close()
  ok(n,'no page errors',not errs,errs); print(n,'errors during reload (cancelled fetch, informational):',navErrs)
  await c.close(); await b.close()
async def main():
  async with async_playwright() as p:
    for n in BROWSERS: await run(p,n)
  f=[k for k,v in R if not v]; print(f'PASSED {len(R)-len(f)}/{len(R)}'); print('FAILS',f)
asyncio.run(main())
