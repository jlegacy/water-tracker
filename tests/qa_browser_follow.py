"""While I'm moving, the map stays centered on me (North Up and Heading Up), including after a scroll/double-tap zoom.
A drag pauses follow briefly; it resumes on its own once I keep moving (even at slow paddling speed), and Re-center restores it at once.
Regression: any zoom gesture turned follow off, and it only came back above ~3 mph, so slow riders drifted off-screen."""
import sys
from playwright.sync_api import sync_playwright
URL=sys.argv[1]; R=[]
# slow mover: GPS speed 1.0 m/s (below the 3 mph 'moving' threshold), ~3.3 m north-east every 500 ms
GEO="""(()=>{let i=0;const mk=()=>{i++;return {coords:{latitude:35.807+i*0.00003,longitude:-77.378+i*0.00001,accuracy:5,heading:70,speed:1.0},timestamp:Date.now()}};
const g={getCurrentPosition(ok){setTimeout(()=>ok(mk()),200)},watchPosition(ok){setTimeout(()=>ok(mk()),200);setInterval(()=>ok(mk()),500);return 1},clearWatch(){}};
Object.defineProperty(navigator,'geolocation',{get:()=>g});})()"""
OFF="()=>{const s=map.getSize(),p=map.latLngToContainerPoint(myLatLng);return [Math.round(Math.hypot(p.x-s.x/2,p.y-s.y/2)),followMe]}"
def ok(k,v,d=''): R.append(bool(v)); print(k,'PASS' if v else 'FAIL',d)
with sync_playwright() as p:
  for n in sys.argv[2:] or ['chromium','webkit']:
    kw=dict(p.devices['iPhone 15']) if n=='webkit' else {'viewport':{'width':393,'height':852},'has_touch':True}; kw.pop('default_browser_type',None)
    b=getattr(p,n).launch(); errs=[]
    c=b.new_context(**kw); c.route('**/*onrender.com*/**',lambda r:r.abort()); c.add_init_script(GEO)
    pg=c.new_page(); pg.on('pageerror',lambda e:errs.append(str(e))); pg.goto(URL); pg.fill('#startName','Follow '+n); pg.evaluate('startApp()')
    pg.wait_for_function("()=>myLatLng&&riders[me]",timeout=15000); pg.wait_for_timeout(2500)
    ok(f'{n} follow on by default',pg.evaluate('followMe'))
    for mode in ('north','heading'):
      pg.evaluate(f"()=>{{headingMode='{mode}';updateHeadingBtn();applyBearing()}}")
      worst=0
      for _ in range(6): pg.wait_for_timeout(700); worst=max(worst,pg.evaluate(OFF)[0])
      ok(f'{n} {mode}: centered while moving',worst<=4,worst)
    pg.evaluate("()=>{headingMode='north';updateHeadingBtn();applyBearing()}"); pg.wait_for_timeout(600)
    s=pg.evaluate("map.getSize()"); x,y=s['x']//2+90,s['y']//2+150
    z0=pg.evaluate('map.getZoom()')
    if n=='chromium': pg.mouse.move(x,y); pg.mouse.wheel(0,-300)
    else: pg.evaluate("([x,y])=>{const r=map.getContainer().getBoundingClientRect();map.getContainer().dispatchEvent(new WheelEvent('wheel',{deltaY:-300,clientX:r.x+x,clientY:r.y+y,bubbles:true,cancelable:true}))}",[x,y])  # mobile WebKit has no mouse.wheel
    pg.wait_for_timeout(1500)
    d,f=pg.evaluate(OFF); ok(f'{n} scroll zoom off-center: still following + centered',f and d<=4 and pg.evaluate('map.getZoom()')!=z0,[d,f])
    pg.mouse.dblclick(x,y); pg.wait_for_timeout(1500)
    d,f=pg.evaluate(OFF); ok(f'{n} double-tap zoom off-center: still following + centered',f and d<=4,[d,f])
    # drag away (real pan) pauses follow
    pg.mouse.move(200,400); pg.mouse.down(); pg.mouse.move(60,250,steps=8); pg.mouse.up(); pg.wait_for_timeout(1200)
    d,f=pg.evaluate(OFF); ok(f'{n} drag pauses follow',(not f) and d>40,[d,f])
    pg.wait_for_timeout(6500)
    for _ in range(24):  # pan animation may still be settling
      d,f=pg.evaluate(OFF)
      if f and d<=4: break
      pg.wait_for_timeout(250)
    ok(f'{n} follow resumes after grace while slowly moving',f and d<=4,[d,f])
    pg.mouse.move(200,400); pg.mouse.down(); pg.mouse.move(60,250,steps=8); pg.mouse.up(); pg.wait_for_timeout(600)
    pg.evaluate('recenter()'); pg.wait_for_timeout(2500)
    d,f=pg.evaluate(OFF); ok(f'{n} Re-center restores follow immediately',f and d<=4,[d,f])
    ok(f'{n} no page errors',not errs,errs); b.close()
print('ALL PASS' if all(R) else 'SOME FAIL')
