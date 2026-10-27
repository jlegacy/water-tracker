"""Browser QA: Relive-style freemium — free users keep only the live ride trail; Premium keeps history + Past.
Uses window.__WT_SET_PREMIUM__ / ?premium= override (no real StoreKit in browser).
Usage: python qa_browser_premium.py http://172.30.0.2:8777/ [chromium|webkit]"""
import asyncio, sys
from playwright.async_api import async_playwright
BASE = sys.argv[1]
BROWSERS = sys.argv[2:] or ['chromium', 'webkit']
INIT = """(()=>{let i=0;const mk=()=>({coords:{latitude:35.807+(i++)*0.0004,longitude:-77.378,accuracy:5,heading:null,speed:3},timestamp:Date.now()});
const g={getCurrentPosition(ok){setTimeout(()=>ok(mk()),300)},watchPosition(ok){setTimeout(()=>ok(mk()),300);setInterval(()=>ok(mk()),500);return 1},clearWatch(){}};
Object.defineProperty(navigator,'geolocation',{get:()=>g});})()"""
R = []
def ok(n, k, v, d=''):
  R.append((n + ' ' + k, bool(v)))
  print(n, k, 'PASS' if v else 'FAIL', d if not v else '')

async def join(pg, name, premium=None):
  url = BASE
  if premium is True: url += ('&' if '?' in url else '?') + 'premium=1'
  if premium is False: url += ('&' if '?' in url else '?') + 'premium=0'
  await pg.goto(url)
  await pg.wait_for_timeout(900)
  await pg.fill('#startName', name)
  await pg.evaluate("()=>startApp()")
  await pg.wait_for_timeout(1500)

async def run(p, n):
  if n == 'webkit':
    dev = dict(p.devices['iPhone 15']); dev.pop('default_browser_type', None)
    b = await p.webkit.launch(); c = await b.new_context(**dev)
  else:
    b = await p.chromium.launch(); c = await b.new_context()
  await c.route('**/*onrender.com*/**', lambda r: r.abort())
  await c.add_init_script(INIT)
  pg = await c.new_page()
  errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))

  # --- Free: live trail records, but no archive / Past / restore ---
  await join(pg, f'QA free {n}', premium=False)
  await pg.wait_for_timeout(10000)
  free_bc = await pg.evaluate("()=>breadcrumb.length")
  ok(n, 'free live breadcrumb records', free_bc >= 3, free_bc)
  free_prem = await pg.evaluate("()=>isPremium()")
  ok(n, 'free override isPremium false', free_prem is False, free_prem)
  await pg.click('#pastBtn')
  await pg.wait_for_timeout(400)
  pay_vis = await pg.evaluate("()=>document.getElementById('paywall').classList.contains('show')")
  past_vis = await pg.evaluate("()=>document.getElementById('pastRides').classList.contains('show')")
  ok(n, 'free Past opens paywall not Past panel', pay_vis and not past_vis, (pay_vis, past_vis))
  web_only = await pg.evaluate("()=>document.getElementById('paywallWebOnly').style.display!=='none'")
  ok(n, 'web paywall says available in iPhone app', web_only)
  await pg.evaluate("()=>closePaywall()")
  await pg.reload(); await pg.wait_for_timeout(1200)
  await join(pg, f'QA free2 {n}', premium=False)
  await pg.wait_for_timeout(2000)
  restored = await pg.evaluate("()=>{let n=0,p=0;if(myPastLayer)myPastLayer.eachLayer(l=>{n++;p+=l.getLatLngs().length});return [n,p]}")
  ok(n, 'free rejoin does not restore past trails', restored[0] == 0 and restored[1] == 0, restored)

  # --- Premium: archive + Past ---
  await pg.evaluate("()=>window.__WT_SET_PREMIUM__(true)")
  ok(n, 'dev override flips to premium', await pg.evaluate("()=>isPremium()") is True)
  await pg.wait_for_timeout(10000)
  prem_bc = await pg.evaluate("()=>breadcrumb.length")
  ok(n, 'premium live breadcrumb records', prem_bc >= 3, prem_bc)
  # Force archive as if leaving
  await pg.evaluate("async()=>{await archiveCurrentRide('qa'); await showMyRecentTrails()}")
  await pg.wait_for_timeout(800)
  past_count = await pg.evaluate("()=>{let n=0;if(myPastLayer)myPastLayer.eachLayer(()=>n++);return n}")
  ok(n, 'premium archives trail onto map', past_count >= 1, past_count)
  await pg.click('#pastBtn')
  await pg.wait_for_timeout(500)
  past_open = await pg.evaluate("()=>document.getElementById('pastRides').classList.contains('show')")
  pay_open = await pg.evaluate("()=>document.getElementById('paywall').classList.contains('show')")
  ok(n, 'premium Past opens Past panel', past_open and not pay_open, (past_open, pay_open))
  await pg.evaluate("()=>closePastRides()")
  await pg.reload(); await pg.wait_for_timeout(1200)
  await join(pg, f'QA prem2 {n}', premium=True)
  await pg.wait_for_timeout(2500)
  restored2 = await pg.evaluate("()=>{let n=0,p=0;if(myPastLayer)myPastLayer.eachLayer(l=>{n++;p+=l.getLatLngs().length});return [n,p]}")
  ok(n, 'premium rejoin restores trail history', restored2[0] >= 1 and restored2[1] >= 1, restored2)

  # Config knobs present
  ids = await pg.evaluate("()=>[PREMIUM.products.monthly, PREMIUM.products.yearly, PREMIUM.groupName, PREMIUM.enabled]")
  ok(n, 'product IDs configured', ids[0] == 'com.encsr.watertracker.premium.monthly' and ids[1] == 'com.encsr.watertracker.premium.yearly', ids)

  errs = [e for e in errs if 'access control' not in e]
  ok(n, 'no page errors', not errs, errs)
  try: await pg.evaluate("()=>{try{ws&&ws.send(JSON.stringify({type:'leave'}))}catch(e){}}")
  except: pass
  await c.close(); await b.close()

async def main():
  async with async_playwright() as p:
    for n in BROWSERS:
      await run(p, n)
  f = [k for k, v in R if not v]
  print('ALL PASS' if not f else 'FAILED: ' + ', '.join(f))
  sys.exit(1 if f else 0)
asyncio.run(main())
