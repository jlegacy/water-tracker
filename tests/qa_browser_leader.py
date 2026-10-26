import sys
from playwright.sync_api import sync_playwright
INIT="""(()=>{const mk=()=>({coords:{latitude:35.807,longitude:-77.378,accuracy:5,heading:null,speed:null},timestamp:Date.now()});
const g={getCurrentPosition(ok){setTimeout(()=>ok(mk()),200)},watchPosition(ok){setTimeout(()=>ok(mk()),200);return 1},clearWatch(){}};
Object.defineProperty(navigator,'geolocation',{get:()=>g});})()"""
CS="()=>{const s=getComputedStyle(document.getElementById('leaderBtn'));return [s.backgroundColor,s.color,leader]}"
with sync_playwright() as p:
  for n in ('chromium','webkit'):
    kw=dict(p.devices['iPhone 15']) if n=='webkit' else {}; kw.pop('default_browser_type',None)
    b=getattr(p,n).launch(); c=b.new_context(**kw); c.route('**/*onrender.com*/**',lambda r:r.abort()); c.add_init_script(INIT)
    pg=c.new_page(); e=[]; pg.on('pageerror',lambda x:e.append(str(x)))
    pg.goto(sys.argv[1]); pg.fill('#startName','QA Lead '+n); pg.evaluate('startApp()'); pg.wait_for_timeout(1500)
    off0=pg.evaluate(CS); pg.screenshot(path=f'/workspace/leader_{n}_off.png')
    pg.click('#leaderBtn'); pg.wait_for_timeout(1200); on=pg.evaluate(CS)
    mk=pg.evaluate("()=>{const els=[...document.querySelectorAll('.leaflet-marker-icon *')].map(x=>getComputedStyle(x).backgroundColor);return els.includes('rgb(139, 92, 246)')}")
    pg.screenshot(path=f'/workspace/leader_{n}_on.png')
    pg.click('#leaderBtn'); pg.wait_for_timeout(500); off1=pg.evaluate(CS)
    ok=on[0]=='rgb(139, 92, 246)' and on[1]=='rgb(255, 255, 255)' and on[2] and mk and off1==off0 and off0[0]=='rgb(71, 85, 105)' and not e
    print(n,'PASS' if ok else 'FAIL',dict(off=off0,on=on,markerPurple=mk,offAgain=off1,errs=e))
    pg.evaluate("ws.send(JSON.stringify({type:'leave'}))"); b.close()
