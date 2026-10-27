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
def proxy_to(route,base):
  u=route.request.url.replace(base,URL,1)
  try: route.fulfill(response=route.fetch(url=u))
  except Exception: route.abort()
ANDROID="""%s window.__buys=[];
window.Capacitor={isNativePlatform:()=>true,getPlatform:()=>'android',Plugins:{NativePurchases:new Proxy({},{get:(_,k)=>async(o)=>{
 if(k==='purchaseProduct'){window.__buys.push(o);return {productIdentifier:o.productIdentifier}}
 if(k==='isBillingSupported')return {isBillingSupported:true}; if(k==='getProducts')return {products:[]};
 if(k==='getPurchases')return {purchases:[]}; return {}; }})}};"""
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
    # --- simulated Android native (Capacitor on https://localhost): debug flag gates overrides; purchases pass planIdentifier
    for dbg in (True,False):
      c=b.new_context(); c.route('https://localhost/**',lambda r:proxy_to(r,'https://localhost/')); c.route('**/*onrender.com*/**',lambda r:r.abort())
      c.add_init_script(ANDROID%('window.__WT_DEBUG_BUILD__=true;' if dbg else ''))
      pg=c.new_page(); pg.on('pageerror',lambda e:errs.append(str(e)))
      pg.goto('https://localhost/'); pg.wait_for_timeout(1000)
      tag='android debug' if dbg else 'android release'
      ok(f'{n} {tag}: native platform detected',pg.evaluate('isNativeApp()&&isAndroidNative()') is True)
      got=pg.evaluate('__WT_SET_PREMIUM__(true)')
      ok(f'{n} {tag}: __WT_SET_PREMIUM__(true) '+('unlocks' if dbg else 'ignored'),got is dbg,got)
      if not dbg:
        pg.evaluate("localStorage.setItem('wtDevPremium','1')"); pg.reload(); pg.wait_for_timeout(1000)
        ok(f'{n} android release: stale wtDevPremium ignored + scrubbed',pg.evaluate('isPremium()') is False and pg.evaluate("localStorage.getItem('wtDevPremium')") is None)
      else:
        pg.evaluate('__WT_SET_PREMIUM__(false)')
        for kind in ('monthly','yearly'):
          pg.evaluate(f"purchasePremium('{kind}')"); pg.wait_for_timeout(300)
          a=pg.evaluate("window.__buys[window.__buys.length-1]")
          ok(f'{n} android purchase {kind}: planIdentifier passed',a and a.get('planIdentifier')==kind and a.get('productIdentifier','').endswith(kind),a)
      c.close()
    ok(f'{n} no page errors',not errs,errs[:2]); b.close()
print('ALL PASS' if all(R) else 'SOME FAIL')
