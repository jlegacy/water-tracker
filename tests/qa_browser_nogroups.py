import asyncio, sys, json, time, websockets
from playwright.async_api import async_playwright
URL=sys.argv[1]; WS=URL.replace('http','ws')+'ws'
BROWSERS=sys.argv[2:] or ['chromium','webkit']
LAT0,LON0=35.807,-77.378; MI=1/69.05
LON=[LON0]  # per-browser area (5 deg lon apart) so riders left by one browser run never show in the next
INIT="""(()=>{const mk=()=>({coords:{latitude:%f,longitude:%f,accuracy:5,heading:null,speed:null},timestamp:Date.now()});
const g={getCurrentPosition(ok){setTimeout(()=>ok(mk()),3000)},watchPosition(ok){setTimeout(()=>ok(mk()),3000);setInterval(()=>ok(mk()),4000);return 1},clearWatch(){}};
Object.defineProperty(navigator,'geolocation',{get:()=>g});})()"""
R=[]
def ok(n,k,v,d=''): R.append((n+' '+k,bool(v))); print(n,k,'PASS' if v else 'FAIL',d if not v else '')
class F:
  def __init__(s,rid,**kw): s.id=rid; s.kw=kw; s.msgs=[]
  async def open(s,mi):
    s.ws=await websockets.connect(WS); await s.ws.send(json.dumps(dict(type='join',id=s.id,name=s.id,**{'range':25,**s.kw})))
    s.t=asyncio.create_task(s.rx()); await s.move(mi); return s
  async def rx(s):
    try:
      async for m in s.ws: s.msgs.append(json.loads(m))
    except Exception: pass
  async def move(s,mi): await s.ws.send(json.dumps(dict(type='pos',lat=LAT0+mi*MI,lon=LON[0],ts=time.time()*1000)))
  async def send(s,**m): await s.ws.send(json.dumps(m))
  async def close(s): await s.send(type='leave'); await s.ws.close()
async def run(p,n):
  LON[0]=LON0+5*BROWSERS.index(n)
  if n=='webkit':
    dev=dict(p.devices['iPhone 15']); dev.pop('default_browser_type',None); b=await p.webkit.launch(); c=await b.new_context(**dev)
  else: b=await p.chromium.launch(); c=await b.new_context()
  await c.route('**/*onrender.com*/**',lambda r:r.abort()); await c.add_init_script(INIT%(LAT0,LON[0]))
  pg=await c.new_page(); errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)))
  await pg.goto(URL); await pg.wait_for_timeout(1500)
  gone=await pg.evaluate("()=>[!!document.getElementById('startGroup'),!!document.getElementById('groupDisplay'),typeof switchGroup]")
  ok(n,'group pickers gone',gone==[False,False,'undefined'],gone)
  txt=await pg.evaluate("()=>document.getElementById('startScreen')?document.getElementById('startScreen').innerText:document.body.innerText")
  ok(n,'join screen says 5 miles','within 5 miles' in txt,txt[:200])
  await pg.fill('#startName',f'QA {n}'); await pg.evaluate("()=>startApp()"); await pg.wait_for_timeout(800)
  st=await pg.evaluate("()=>document.getElementById('status').textContent")
  ok(n,'waiting for location before fix',st=='Waiting for location…',st)
  await pg.wait_for_timeout(3500)
  st=await pg.evaluate("()=>document.getElementById('status').textContent")
  ok(n,'sharing after fix',st=='Sharing — riders within 5 mi',st)
  await pg.evaluate("()=>setRange(25)"); await pg.wait_for_timeout(500)  # scenario below uses 25 mi geometry
  me=await pg.evaluate("()=>me")
  a=await F(f'{n}-A24',leader=True).open(24); b=await F(f'{n}-B26').open(-26); cc=await F(f'{n}-C28').open(-28); l2=await F(f'{n}-L2',leader=True).open(5)
  await pg.wait_for_timeout(2500)
  L="()=>[...document.getElementById('riderList').options].map(o=>o.textContent)"
  lst=await pg.evaluate(L); ids=await pg.evaluate("()=>Object.keys(positions).filter(k=>k!==me).sort()")
  ok(n,'only riders <=25mi listed',sorted(ids)==sorted([f'{n}-A24',f'{n}-L2']),[ids,lst])
  ok(n,'two leaders badged ★',sum('★' in x and 'Leader' in x for x in lst)==2,lst)
  en=await pg.evaluate("()=>[document.getElementById('riderBtn').disabled,document.getElementById('riderList').disabled]")
  ok(n,'dropdown enabled with riders',en==[False,False],en)
  await a.move(26.5); await pg.wait_for_timeout(1500); ids=await pg.evaluate("()=>Object.keys(positions)")
  ok(n,'hysteresis: 26.5mi still shown',f'{n}-A24' in ids,ids)
  await b.move(-26.5); await pg.wait_for_timeout(1500); ids=await pg.evaluate("()=>Object.keys(positions)")
  ok(n,'hysteresis: never-shown at 26.5 stays hidden',f'{n}-B26' not in ids,ids)
  await a.move(27.5); await pg.wait_for_timeout(1500); ids=await pg.evaluate("()=>Object.keys(positions)")
  ok(n,'past 27mi removed (leave)',f'{n}-A24' not in ids,ids)
  await a.move(24); await pg.wait_for_timeout(1500); ids=await pg.evaluate("()=>Object.keys(positions)")
  ok(n,'re-entry at 24mi shown',f'{n}-A24' in ids,ids)
  await cc.send(type='sos',on=True); await pg.wait_for_timeout(1500)
  sos=await pg.evaluate("()=>[collectSosRiders().map(r=>r.id||r.name), document.getElementById('sosBar').style.display]")
  ok(n,'far SOS not shown',not any('C28' in str(x) for x in sos[0]) and sos[1]=='none',sos)
  await l2.send(type='sos',on=True); await pg.wait_for_timeout(1500)
  sos=await pg.evaluate("()=>[JSON.stringify(collectSosRiders()), document.getElementById('sosBar').style.display, document.getElementById('sosBar').innerText]")
  ok(n,'near SOS shown',f'{n}-L2' in sos[0] and sos[1]!='none',sos)
  await l2.send(type='broadcast',text='hello all'); await pg.wait_for_timeout(800)
  bn=await pg.evaluate("()=>document.getElementById('banner').innerText")
  ok(n,'all-message from near rider',"hello all" in bn,bn)
  await cc.send(type='broadcast',text='far all'); await pg.wait_for_timeout(800)
  bn=await pg.evaluate("()=>document.getElementById('banner').innerText")
  ok(n,'all-message from far rider not received',"far all" not in bn,bn)
  await cc.send(type='msg',to=me,text='direct far'); await pg.wait_for_timeout(800)
  bn=await pg.evaluate("()=>document.getElementById('banner').innerText")
  ok(n,'direct message by id (any distance)',"direct far" in bn,bn)
  a.msgs.clear(); await pg.evaluate(f"()=>{{document.getElementById('riderList').value='{n}-A24';document.getElementById('msgText').value='hi A';sendMessage()}}"); await pg.wait_for_timeout(800)
  ok(n,'UI direct msg delivered',any(m.get('type')=='msg' and m.get('text')=='hi A' for m in a.msgs),a.msgs[-3:])
  a.msgs.clear(); cc.msgs.clear(); await pg.evaluate("()=>{document.getElementById('riderList').value='';document.getElementById('msgText').value='hi everyone';sendMessage()}"); await pg.wait_for_timeout(800)
  ga=any(m.get('text')=='hi everyone' for m in a.msgs); gc=any(m.get('text')=='hi everyone' for m in cc.msgs)
  ok(n,'UI all-msg near yes / far no',ga and not gc,[ga,gc])
  await pg.screenshot(path=f'/workspace/nogroups_{n}.png')
  await l2.close(); await pg.wait_for_timeout(1000); ids=await pg.evaluate("()=>Object.keys(positions)")
  ok(n,'explicit leave removes rider',f'{n}-L2' not in ids,ids)
  for f in (a,b,cc): await f.close()
  ok(n,'no page errors',not errs,errs)
  await b.close() if False else None
  await c.close()
async def main():
  async with async_playwright() as p:
    for n in BROWSERS: await run(p,n)
  f=[k for k,v in R if not v]; print(f'PASSED {len(R)-len(f)}/{len(R)}'); print('FAILS',f)
asyncio.run(main())
