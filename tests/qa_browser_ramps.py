"""Ramps button QA. Usage: python qa_browser_ramps.py http://127.0.0.2:8811/"""
import asyncio, sys
from playwright.async_api import async_playwright
URL=sys.argv[1]; R=[]
INIT="""(()=>{const mk=()=>({coords:{latitude:35.807,longitude:-77.378,accuracy:5,heading:null,speed:null},timestamp:Date.now()});
const g={getCurrentPosition(ok){setTimeout(()=>ok(mk()),300)},watchPosition(ok){setTimeout(()=>ok(mk()),300);return 1},clearWatch(){}};
Object.defineProperty(navigator,'geolocation',{get:()=>g});})()"""
def ok(k,v,d=''): R.append((k,bool(v))); print(k,'PASS' if v else 'FAIL',d)
async def run(p,n,block):
  if n=='webkit':
    dev=dict(p.devices['iPhone 15']); dev.pop('default_browser_type',None); b=await p.webkit.launch(); c=await b.new_context(**dev)
  else: b=await p.chromium.launch(); c=await b.new_context()
  await c.route('**/*onrender.com*/**',lambda r:r.abort())
  reqs=[]
  if block: await c.route('**/ramps_us.json',lambda r:r.fulfill(status=404,body='nope'))
  await c.add_init_script(INIT); pg=await c.new_page(); errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)))
  pg.on('request',lambda r:reqs.append(r.url) if 'ramp' in r.url else None)
  await pg.goto(URL); await pg.fill('#startName','QA Ramps'); await pg.evaluate("startApp()"); await pg.wait_for_timeout(1500)
  await pg.click('#rampsBtn'); await pg.wait_for_timeout(3000)
  s=await pg.evaluate("()=>[document.getElementById('rampToast').textContent,rampItems.length,document.querySelectorAll('.rampIcon').length,document.getElementById('rampsBtn').textContent]")
  tag=f"{n} {'fallback /api/ramps' if block else 'ramps_us.json'}:"
  ok(tag+' markers + count toast',s[1]>0 and s[2]>0 and s[0].startswith(f"{s[1]} ramps/marinas nearby") and s[3]=='Hide Ramps',s)
  ok(tag+' used expected source',any('/api/ramps' in u for u in reqs) if block else any(u.endswith('/ramps_us.json') for u in reqs),reqs)
  ok(tag+' no page errors',not errs,errs)
  await b.close()
async def main():
  async with async_playwright() as p:
    for n in ('chromium','webkit'):
      for block in (False,True): await run(p,n,block)
  f=[k for k,v in R if not v]; print(f'PASSED {len(R)-len(f)}/{len(R)}','FAILS',f)
asyncio.run(main())
