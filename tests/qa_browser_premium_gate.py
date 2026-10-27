"""Premium dev/QA overrides (?premium=1, localStorage wtDevPremium, __WT_SET_PREMIUM__) work only on local/test builds.
A simulated production host (served from the local server via route) must ignore them and scrub stale values."""
import sys
from playwright.sync_api import sync_playwright
URL=sys.argv[1].rstrip('/')+'/'; R=[]
PROD='https://water-tracker-yz68.onrender.com/'
def ok(k,v,d=''): R.append(bool(v)); print(k,'PASS' if v else 'FAIL',d)
def proxy(route):  # serve the fake production host from the local server
  u=route.request.url.replace(PROD,URL,1)
  try: route.fulfill(response=route.fetch(url=u))
  except Exception: route.abort()
with sync_playwright() as p:
  for n in sys.argv[2:] or ['chromium','webkit']:
    b=getattr(p,n).launch(); errs=[]
    # --- local test host: overrides honored
    c=b.new_context(); c.route('**/*onrender.com*/**',lambda r:r.abort()); pg=c.new_page(); pg.on('pageerror',lambda e:errs.append(str(e)))
    pg.goto(URL+'?premium=1'); pg.wait_for_timeout(800)
    ok(f'{n} local: ?premium=1 unlocks',pg.evaluate('isPremium()') is True)
    pg.goto(URL); pg.evaluate("localStorage.setItem('wtDevPremium','1')"); pg.reload(); pg.wait_for_timeout(800)
    ok(f'{n} local: wtDevPremium=1 unlocks',pg.evaluate('isPremium()') is True)
    ok(f'{n} local: __WT_SET_PREMIUM__(false) locks',pg.evaluate('__WT_SET_PREMIUM__(false)') is False)
    G=pg.evaluate("""()=>({prod:devOverrideHostAllowed('water-tracker-yz68.onrender.com'),lh:devOverrideHostAllowed('localhost'),
      lo:devOverrideHostAllowed('127.0.0.1'),t:devOverrideHostAllowed('172.30.0.2'),p10:devOverrideHostAllowed('10.1.2.3'),p192:devOverrideHostAllowed('192.168.1.5'),
      pub172:devOverrideHostAllowed('172.32.0.1'),pub:devOverrideHostAllowed('8.8.8.8'),trick:devOverrideHostAllowed('192.168.1.5.evil.com'),
      natRel:devOverridesAllowed({native:true,debug:undefined}),natDbg:devOverridesAllowed({native:true,debug:true}),natHost:devOverridesAllowed({native:true,host:'localhost'})})""")
    want={'prod':False,'lh':True,'lo':True,'t':True,'p10':True,'p192':True,'pub172':False,'pub':False,'trick':False,'natRel':False,'natDbg':True,'natHost':False}
    ok(f'{n} gate function by host / native debug flag',G==want,G)
    c.close()
    # --- simulated production host: overrides ignored, stale values scrubbed
    c=b.new_context(); c.route(PROD+'**',proxy); pg=c.new_page(); pg.on('pageerror',lambda e:errs.append(str(e)))
    pg.goto(PROD+'?premium=1'); pg.wait_for_timeout(1000)
    ok(f'{n} prod: ?premium=1 ignored',pg.evaluate('isPremium()') is False)
    pg.evaluate("""()=>{localStorage.setItem('wtDevPremium','1');localStorage.setItem('wtPremiumEntitlement',JSON.stringify({active:true,productId:'dev-override'}))}""")
    pg.goto(PROD); pg.wait_for_timeout(1000)
    ok(f'{n} prod: stale wtDevPremium + dev-override cache ignored',pg.evaluate('isPremium()') is False)
    st=pg.evaluate("[localStorage.getItem('wtDevPremium'),localStorage.getItem('wtPremiumEntitlement')]")
    ok(f'{n} prod: stale values scrubbed from localStorage',st==[None,None],st)
    ok(f'{n} prod: __WT_SET_PREMIUM__(true) ignored',pg.evaluate('__WT_SET_PREMIUM__(true)') is False and pg.evaluate("localStorage.getItem('wtDevPremium')") is None)
    ok(f'{n} prod: window.__WT_PREMIUM__=true ignored',pg.evaluate('()=>{window.__WT_PREMIUM__=true;return isPremium()}') is False)
    c.close()
    ok(f'{n} no page errors',not errs,errs[:2]); b.close()
print('ALL PASS' if all(R) else 'SOME FAIL')
