"""Browser QA: cold start. Map opens on last-known spot; 'Searching for your location…' bar until first fix; hint after 15 s; first fix centers+fits.
Usage: python qa_browser_coldstart.py http://172.30.0.2:8777/ [chromium|webkit]"""
import asyncio, sys
from playwright.async_api import async_playwright
URL=sys.argv[1]; BROWSERS=sys.argv[2:] or ['chromium','webkit']
R=[]
def ok(n,k,v,d=''): R.append((n+' '+k,bool(v))); print(n,k,'PASS' if v else 'FAIL',d if not v else '')
def init(lat,lon,delay):  # delay<0: never answer
  return """(()=>{const mk=()=>({coords:{latitude:%f,longitude:%f,accuracy:5,heading:null,speed:null},timestamp:Date.now()});const D=%d;
const g={getCurrentPosition(ok){if(D>=0)setTimeout(()=>ok(mk()),D)},watchPosition(ok){if(D>=0){setTimeout(()=>ok(mk()),D);setInterval(()=>ok(mk()),3000)}return 1},clearWatch(){}};
Object.defineProperty(navigator,'geolocation',{get:()=>g});})()"""%(lat,lon,delay)
ST="()=>{const b=document.getElementById('locBar'),c=map.getCenter();return {bar:b.style.display!=='none'?document.getElementById('locBarText').textContent:'',hint:b.classList.contains('hint'),lat:c.lat,lon:c.lng,z:map.getZoom(),fit:myLatLng?rangeZoomFor(myRange):null,map:document.getElementById('map').style.display}}"
async def ctx(p,n):
  if n=='webkit':
    dev=dict(p.devices['iPhone 15']); dev.pop('default_browser_type',None); b=await p.webkit.launch(); c=await b.new_context(**dev)
  else: b=await p.chromium.launch(); c=await b.new_context(viewport={'width':393,'height':852})
  await c.route('**/*onrender.com*/**',lambda r:r.abort()); return b,c
async def page(c,n,errs):
  pg=await c.new_page(); pg.on('pageerror',lambda e:errs.append(str(e))); return pg
async def run(p,n):
  lat,lon=36.1,-76.2; errs=[]
  b,c=await ctx(p,n); await c.add_init_script(init(lat,lon,4000)); pg=await page(c,n,errs)
  await pg.goto(URL); await pg.wait_for_timeout(600)
  await pg.fill('#startName',f'QA CS {n}'); t0=await pg.evaluate("()=>{startApp();return performance.now()}"); await pg.wait_for_timeout(300)
  s=await pg.evaluate(ST); ok(n,'map shown + Searching bar right away',s['map']=='block' and s['bar'].startswith('Searching for your location'),s)
  ok(n,'existing bottom status bar kept',await pg.evaluate("()=>document.getElementById('status').style.display")=='block')
  await pg.screenshot(path=f'/workspace/coldstart_searching_{n}.png')
  t=await pg.evaluate("""(t0)=>new Promise(r=>{const f=()=>{if(document.getElementById('locBar').style.display==='none')r(performance.now()-t0);else setTimeout(f,50)};f()})""",t0)
  s=await pg.evaluate(ST); ok(n,'bar hidden on first fix; map centered+fitted on fix',not s['bar'] and abs(s['lat']-lat)<0.01 and abs(s['lon']-lon)<0.01 and abs(s['z']-s['fit'])<0.05,s)
  print(n,'time to centered view after fix ms',round(t))
  stored=await pg.evaluate("()=>localStorage.getItem('trackerLastPos')"); ok(n,'last position saved',stored and '36.1' in stored,stored)
  await pg.evaluate("()=>{try{ws.send(JSON.stringify({type:'leave'}))}catch(e){}}"); await pg.close()
  # reload with GPS that never answers: map opens on saved spot before any fix; hint after 15 s
  await c.close(); c2=await b.new_context(**({**{k:v for k,v in p.devices['iPhone 15'].items() if k!='default_browser_type'}} if n=='webkit' else {'viewport':{'width':393,'height':852}}))
  await c2.route('**/*onrender.com*/**',lambda r:r.abort()); await c2.add_init_script(init(lat,lon,-1))
  await c2.add_init_script("try{localStorage.setItem('trackerLastPos',JSON.stringify({lat:36.1,lon:-76.2,t:Date.now()}))}catch(e){}")
  pg=await page(c2,n,errs); await pg.goto(URL); await pg.wait_for_timeout(600)
  s=await pg.evaluate(ST); ok(n,'cold load opens on last-known spot (not default)',abs(s['lat']-lat)<0.01 and abs(s['lon']-lon)<0.01,s)
  await pg.fill('#startName',f'QA CS2 {n}'); await pg.evaluate("()=>startApp()"); await pg.wait_for_timeout(15800)
  s=await pg.evaluate(ST); ok(n,'after 15 s: permission hint in same bar',s['hint'] and 'Location is allowed' in s['bar'],s)
  if n=='webkit': await pg.screenshot(path='/workspace/coldstart_hint_webkit.png')
  ok(n,'map still interactive behind bar',await pg.evaluate("()=>map.dragging.enabled() && getComputedStyle(document.getElementById('locBar')).position==='absolute'"))
  await pg.evaluate("()=>{try{ws.send(JSON.stringify({type:'leave'}))}catch(e){}}")
  ok(n,'no page errors',not errs,errs); await b.close()
async def main():
  async with async_playwright() as p:
    for n in BROWSERS: await run(p,n)
  f=[k for k,v in R if not v]; print('ALL PASS' if not f else 'FAILED: '+', '.join(f)); sys.exit(1 if f else 0)
asyncio.run(main())
