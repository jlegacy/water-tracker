"""Breadcrumb trail starts only from fresh, accurate GPS fixes after joining.
Regression: joining with breadcrumbs on drew a line from ~0.5 mi away (saved last spot / rough or cached first fix) to the real spot."""
import sys, math
from playwright.sync_api import sync_playwright
URL=sys.argv[1].rstrip('/')+'/?premium=1'; R=[]
REAL=(35.807,-77.378); FAR=(35.807+0.0072,-77.378)  # ~800 m north
def geo(mode): return """(()=>{const REAL=[%f,%f],FAR=[%f,%f],MODE='%s';let i=0;
const fix=(ll,acc,ageMs,spd)=>({coords:{latitude:ll[0],longitude:ll[1],accuracy:acc,heading:null,speed:spd},timestamp:Date.now()-ageMs});
const next=()=>{i++;
  if(MODE==='ride'){return fix([REAL[0]+i*0.0001,REAL[1]],5,0,4)}
  if(i===1){ if(MODE==='coarse')return fix(FAR,1500,0,null); if(MODE==='stale')return fix(FAR,5,120000,null); if(MODE==='jump')return fix(FAR,8,0,null);}
  const j=(i%%3-1)*0.00002; return fix([REAL[0]+j,REAL[1]-j],5,0,0)};
const g={getCurrentPosition(ok,err,o){setTimeout(()=>ok(o&&o.enableHighAccuracy===false?fix(FAR,2000,600000,null):next()),100)},
  watchPosition(ok){setTimeout(()=>ok(next()),MODE==='storeunlock'?2500:600);setInterval(()=>ok(next()),3100);return 1},clearWatch(){}};
Object.defineProperty(navigator,'geolocation',{get:()=>g});
localStorage.setItem('trackerLastPos',JSON.stringify({lat:FAR[0],lon:FAR[1],t:Date.now()-3600000}));})()"""%(REAL+FAR+(mode,))
def dist(a,b): return 6371000*math.hypot(math.radians(a[0]-b[0]),math.radians(a[1]-b[1])*math.cos(math.radians(a[0])))
def ok(k,v,d=''): R.append(bool(v)); print(k,'PASS' if v else 'FAIL',d)
PTS="()=>{const a=breadcrumb.concat(breadcrumbPending).map(p=>[p.lat,p.lon]);const l=breadcrumbLine?breadcrumbLine.getLatLngs().map(p=>[p.lat,p.lng]):[];return [a,l]}"
with sync_playwright() as p:
  for n in sys.argv[2:] or ['chromium','webkit']:
    b=getattr(p,n).launch()
    for mode in ('coarse','stale','jump','storeunlock','ride'):
      errs=[]; c=b.new_context(); c.route('**/*onrender.com*/**',lambda r:r.abort()); c.add_init_script(geo(mode))
      pg=c.new_page(); pg.on('pageerror',lambda e:errs.append(str(e)))
      pg.goto(URL); pg.fill('#startName','Trail '+n); pg.evaluate('startApp()')
      if mode=='storeunlock':  # StoreKit entitlement lands while only the rough/saved spot is known
        pg.wait_for_timeout(1200); pg.evaluate("()=>setPremiumActive(true,'com.encsr.watertracker.premium.monthly')")
      pg.wait_for_timeout(14500)
      ok(f'{n} {mode}: premium + trail on',pg.evaluate('isPremium()&&trailOn'))
      pts,line=pg.evaluate(PTS)
      if mode=='ride':
        span=dist(pts[0],pts[-1]) if len(pts)>1 else 0
        ok(f'{n} ride: real riding recorded',len(pts)>=3 and span>30 and all(dist(x,REAL)<150 for x in pts),[len(pts),round(span)])
      else:
        worst=max([dist(x,REAL) for x in pts+line] or [0])
        ok(f'{n} {mode}: no bogus far point in trail/line',len(pts)>=2 and worst<20,[len(pts),round(worst)])
      ok(f'{n} {mode}: no page errors',not errs,errs[:2]); c.close()
    b.close()
print('ALL PASS' if all(R) else 'SOME FAIL')
