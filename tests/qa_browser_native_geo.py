"""Browser QA: inside the Capacitor app, location comes from the native Geolocation plugin
(never navigator.geolocation, which would trigger WebKit's '"localhost" would like to use your location' prompt).
On the plain web, navigator.geolocation is still used.
Usage: python qa_browser_native_geo.py http://172.30.0.2:8777/ [chromium|webkit]"""
import asyncio, sys
from playwright.async_api import async_playwright
URL=sys.argv[1]; BROWSERS=sys.argv[2:] or ['chromium','webkit']
R=[]
def ok(n,k,v,d=''): R.append((n+' '+k,bool(v))); print(n,k,'PASS' if v else 'FAIL',d if not v else '')
NAV="""(()=>{window.__nav={get:0,watch:0,clear:0};const mk=()=>({coords:{latitude:36.1,longitude:-76.2,accuracy:5,heading:null,speed:null},timestamp:Date.now()});
const g={getCurrentPosition(ok){__nav.get++;setTimeout(()=>ok(mk()),200)},watchPosition(ok){__nav.watch++;setTimeout(()=>ok(mk()),300);return 7},clearWatch(){__nav.clear++}};
Object.defineProperty(navigator,'geolocation',{get:()=>g});})()"""
NATIVE="""(()=>{window.__plug={get:0,watch:0,clear:[]};const mk=()=>({coords:{latitude:35.5,longitude:-75.5,accuracy:5,heading:null,speed:null},timestamp:Date.now()});
window.Capacitor={isNativePlatform:()=>true,getPlatform:()=>'ios',Plugins:{
 Geolocation:{getCurrentPosition(o){__plug.get++;return new Promise(r=>setTimeout(()=>r(mk()),200))},
   watchPosition(o,cb){__plug.watch++;setTimeout(()=>cb(mk()),300);return Promise.resolve('w'+__plug.watch)},
   clearWatch(o){__plug.clear.push(o.id);return Promise.resolve()}},
 BackgroundGeolocation:{addWatcher(){return Promise.reject(new Error('no plugin'))},removeWatcher(){return Promise.resolve()}}}};})()"""
async def ctx(p,n):
  if n=='webkit':
    dev=dict(p.devices['iPhone 15']); dev.pop('default_browser_type',None); b=await p.webkit.launch(); c=await b.new_context(**dev)
  else: b=await p.chromium.launch(); c=await b.new_context(viewport={'width':393,'height':852})
  await c.route('**/*onrender.com*/**',lambda r:r.abort()); return b,c
async def run(p,n):
  errs=[]
  # native: plugin only
  b,c=await ctx(p,n); await c.add_init_script(NAV); await c.add_init_script(NATIVE)
  pg=await c.new_page(); pg.on('pageerror',lambda e:errs.append(str(e)))
  await pg.goto(URL); await pg.wait_for_timeout(600)
  await pg.fill('#startName',f'QA NG {n}'); await pg.evaluate("()=>startApp()"); await pg.wait_for_timeout(1500)
  s=await pg.evaluate("()=>({nav:__nav,plug:__plug,me:myLatLng,w:webWatchId&&webWatchId.id})")
  ok(n,'native: navigator.geolocation never called',s['nav']=={'get':0,'watch':0,'clear':0},s)
  ok(n,'native: plugin rough fix + fallback watch used',s['plug']['get']>=1 and s['plug']['watch']==1 and s['w']=='w1',s)
  ok(n,'native: plugin position reaches the map',s['me'] and abs(s['me'][0]-35.5)<0.01,s)
  await pg.evaluate("()=>{startWebWatch(); nativeOneShotBusy=false; nativeOneShot();}"); await pg.wait_for_timeout(500)
  s=await pg.evaluate("()=>({nav:__nav,plug:__plug})")
  ok(n,'native: restart clears plugin watch; one-shot via plugin; still no navigator calls',s['plug']['clear']==['w1'] and s['plug']['watch']==2 and s['plug']['get']>=2 and s['nav']['get']+s['nav']['watch']==0,s)
  await c.close()
  # plain web: navigator.geolocation
  c=await (b.new_context(**{k:v for k,v in p.devices['iPhone 15'].items() if k!='default_browser_type'}) if n=='webkit' else b.new_context(viewport={'width':393,'height':852}))
  await c.route('**/*onrender.com*/**',lambda r:r.abort()); await c.add_init_script(NAV)
  pg=await c.new_page(); pg.on('pageerror',lambda e:errs.append(str(e)))
  await pg.goto(URL); await pg.wait_for_timeout(600)
  await pg.fill('#startName',f'QA NGW {n}'); await pg.evaluate("()=>startApp()"); await pg.wait_for_timeout(1500)
  s=await pg.evaluate("()=>({nav:__nav,me:myLatLng})")
  ok(n,'web: navigator.geolocation used',s['nav']['get']>=1 and s['nav']['watch']>=1 and s['me'] and abs(s['me'][0]-36.1)<0.01,s)
  ok(n,'no page errors',not errs,errs)
  await b.close()
async def main():
  async with async_playwright() as p:
    for n in BROWSERS: await run(p,n)
  f=[k for k,v in R if not v]; print('ALL PASS' if not f else f'FAILS {f}')
asyncio.run(main())
