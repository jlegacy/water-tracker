"""Browser QA: Relive-style freemium — free users get NO breadcrumbs; Premium draws + keeps trails on map 24h.
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

  # --- Free: no breadcrumbs at all; discovery button opens paywall ---
  await join(pg, f'QA free {n}', premium=False)
  await pg.wait_for_timeout(10000)
  free = await pg.evaluate("()=>({bc:breadcrumb.length, line:!!breadcrumbLine, trailOn, prem:isPremium(), crumbs:document.getElementById('crumbsBtn')&&document.getElementById('crumbsBtn').textContent})")
  ok(n, 'free isPremium false', free['prem'] is False, free)
  ok(n, 'free trailOn false', free['trailOn'] is False, free)
  ok(n, 'free no breadcrumb points', free['bc'] == 0, free)
  ok(n, 'free no breadcrumb line', free['line'] is False, free)
  ok(n, 'free shows Breadcrumbs (Premium) button', 'Premium' in (free['crumbs'] or ''), free)
  await pg.click('#crumbsBtn')
  await pg.wait_for_timeout(400)
  pay_vis = await pg.evaluate("()=>document.getElementById('paywall').classList.contains('show')")
  ok(n, 'free Breadcrumbs button opens paywall', pay_vis)
  await pg.evaluate("()=>closePaywall()")
  past_gone = await pg.evaluate("()=>!document.getElementById('pastBtn') && !document.getElementById('pastRides')")
  ok(n, 'Past rides UI removed', past_gone)

  # --- Premium: live trail + archive onto map ---
  await pg.evaluate("()=>window.__WT_SET_PREMIUM__(true)")
  ok(n, 'dev override flips to premium', await pg.evaluate("()=>isPremium()") is True)
  trail_on = await pg.evaluate("()=>trailOn")
  ok(n, 'premium enables trailOn', trail_on is True, trail_on)
  await pg.wait_for_timeout(10000)
  prem_bc = await pg.evaluate("()=>breadcrumb.length")
  ok(n, 'premium live breadcrumb records', prem_bc >= 3, prem_bc)
  has_line = await pg.evaluate("()=>!!breadcrumbLine")
  ok(n, 'premium draws live breadcrumb line', has_line)
  await pg.evaluate("async()=>{await archiveCurrentRide('qa'); await showMyRecentTrails()}")
  await pg.wait_for_timeout(800)
  past_count = await pg.evaluate("()=>{let n=0;if(myPastLayer)myPastLayer.eachLayer(()=>n++);return n}")
  ok(n, 'premium archives trail onto map', past_count >= 1, past_count)
  await pg.reload(); await pg.wait_for_timeout(1200)
  await join(pg, f'QA prem2 {n}', premium=True)
  await pg.wait_for_timeout(2500)
  restored2 = await pg.evaluate("()=>{let n=0,p=0;if(myPastLayer)myPastLayer.eachLayer(l=>{n++;p+=l.getLatLngs().length});return [n,p]}")
  ok(n, 'premium rejoin restores trails on map', restored2[0] >= 1 and restored2[1] >= 1, restored2)

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
