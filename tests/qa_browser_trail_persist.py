"""Browser QA: a breadcrumb trail made before leaving (reload / sign-out) is back on the map after rejoining.
Usage: python qa_browser_trail_persist.py http://172.30.0.2:8777/ [chromium|webkit]"""
import asyncio, sys
from playwright.async_api import async_playwright
URL=sys.argv[1]; BROWSERS=sys.argv[2:] or ['chromium','webkit']
INIT="""(()=>{let i=0;const mk=()=>({coords:{latitude:35.807+(i++)*0.0004,longitude:-77.378,accuracy:5,heading:null,speed:3},timestamp:Date.now()});
const g={getCurrentPosition(ok){setTimeout(()=>ok(mk()),300)},watchPosition(ok){setTimeout(()=>ok(mk()),300);setInterval(()=>ok(mk()),500);return 1},clearWatch(){}};
Object.defineProperty(navigator,'geolocation',{get:()=>g});})()"""
R=[]
def ok(n,k,v,d=''): R.append((n+' '+k,bool(v))); print(n,k,'PASS' if v else 'FAIL',d if not v else '')
COUNT="()=>{let n=0,p=0;if(myPastLayer)myPastLayer.eachLayer(l=>{n++;p+=l.getLatLngs().length});return [n,p,breadcrumb.length]}"
async def join(pg,n):
  await pg.goto(URL); await pg.wait_for_timeout(800)
  await pg.fill('#startName',f'QA trail {n}'); await pg.evaluate("()=>startApp()")
async def run(p,n):
  if n=='webkit':
    dev=dict(p.devices['iPhone 15']); dev.pop('default_browser_type',None); b=await p.webkit.launch(); c=await b.new_context(**dev)
  else: b=await p.chromium.launch(); c=await b.new_context()
  await c.route('**/*onrender.com*/**',lambda r:r.abort()); await c.add_init_script(INIT)
  pg=await c.new_page(); errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)))
  await join(pg,n); await pg.wait_for_timeout(12000)
  before=await pg.evaluate("()=>breadcrumb.length"); ok(n,'breadcrumb recorded before leaving',before>=3,before)
  await pg.reload(); await pg.wait_for_timeout(1500)   # leave (pagehide archives) and back to sign-in
  await join(pg,n); await pg.wait_for_timeout(2500)
  v=await pg.evaluate(COUNT); ok(n,'trail restored on map after rejoin',v[0]>=1 and v[1]>=before-1,[before,v])
  await pg.evaluate("()=>{window.__now=Date.now;Date.now=()=>window.__now()+25*3600e3}"); await pg.evaluate("()=>purgeExpiredRides()"); await pg.wait_for_timeout(800)
  v=await pg.evaluate("()=>{let n=0;myPastLayer.eachLayer(()=>n++);return n}"); ok(n,'expired (>24 h) trail leaves the map',v==0,v)
  errs=[e for e in errs if 'access control' not in e]; ok(n,'no page errors',not errs,errs)
  await pg.evaluate("()=>{try{ws&&ws.send(JSON.stringify({type:'leave'}))}catch(e){}}"); await c.close(); await b.close()
async def main():
  async with async_playwright() as p:
    for n in BROWSERS: await run(p,n)
  f=[k for k,v in R if not v]; print('ALL PASS' if not f else 'FAILED: '+', '.join(f)); sys.exit(1 if f else 0)
asyncio.run(main())
