import sys
from playwright.sync_api import sync_playwright
INIT="""(()=>{const mk=()=>({coords:{latitude:35.807,longitude:-77.378+%s,accuracy:5,heading:null,speed:null},timestamp:Date.now()});
const g={getCurrentPosition(ok){setTimeout(()=>ok(mk()),200)},watchPosition(ok){setTimeout(()=>ok(mk()),200);return 1},clearWatch(){}};
Object.defineProperty(navigator,'geolocation',{get:()=>g});})()"""
BOX="()=>{const m=map.getContainer().getBoundingClientRect();const ll=rangeCircle.getLatLng();const c=map.latLngToContainerPoint(ll);const e=map.latLngToContainerPoint(L.latLng(ll.lat,ll.lng+rangeCircle.getRadius()/(111320*Math.cos(ll.lat*Math.PI/180))));const rp=Math.hypot(e.x-c.x,e.y-c.y);return {l:c.x-rp,r:c.x+rp,t:m.top+c.y-rp,b:m.top+c.y+rp,w:2*rp/m.width,vw:m.width,vh:m.height,mt:m.top,mb:m.bottom}}"
R=[]
def ok(k,v,d=''): R.append((k,bool(v))); print(k,'PASS' if v else 'FAIL',d)
def inview(b): return b['l']>=-1 and b['r']<=b['vw']+1 and b['t']>=b['mt']-1 and b['b']<=b['mb']+1 and 0.85<=b['w']<=1.0
with sync_playwright() as p:
  for i,n in enumerate(('chromium','webkit')):
    lon=-77.378+i*5
    kw=dict(p.devices['iPhone 15']) if n=='webkit' else {'viewport':{'width':393,'height':852}}; kw.pop('default_browser_type',None)
    b=getattr(p,n).launch(); c=b.new_context(**kw); c.route('**/*onrender.com*/**',lambda r:r.abort()); c.add_init_script(INIT%(i*5))
    pg=c.new_page(); e=[]; pg.on('pageerror',lambda x:e.append(str(x)))
    pg.goto(sys.argv[1]); pg.wait_for_timeout(800); pg.fill('#startName','QA Circle '+n); pg.evaluate('startApp()'); pg.wait_for_timeout(1800)
    s=pg.evaluate("()=>[!!rangeCircle,rangeCircle&&rangeCircle.getRadius(),rangeCircle&&rangeCircle.options.interactive,rangeCircle&&rangeCircle.options.fillOpacity,rangeCircle&&rangeCircle._path.closest('.leaflet-overlay-pane')!=null,getComputedStyle(rangeCircle._path).pointerEvents]")
    ok(f'{n} faint circle shown at start, non-interactive, in overlay pane',s[0] and abs(s[1]-25*1609.344)<1 and s[2] is False and s[3]<=0.08 and s[4] and s[5]=='none',s)
    rad=[]
    for v in (30,35,40,45,50,25):
      pg.click('#bar .cpick.rng .cbtn'); pg.click(f"#bar .cpick.rng .cmenu div:text-is('{v} mi')"); pg.wait_for_timeout(400)
      rad.append(round(pg.evaluate('rangeCircle.getRadius()')/1609.344,3))
    ok(f'{n} radius matches each option',rad==[30,35,40,45,50,25],rad)
    pg.evaluate("map.setZoom(12)"); pg.wait_for_timeout(300)
    for a,z in ((25,50),(50,25)):
      pg.click('#bar .cpick.rng .cbtn'); pg.click(f"#bar .cpick.rng .cmenu div:text-is('{z} mi')"); pg.wait_for_timeout(700)
      bx=pg.evaluate(BOX); ok(f'{n} {a}->{z}: whole circle visible, ~screen width',inview(bx),{k:round(v,2) for k,v in bx.items()})
      pg.screenshot(path=f'/workspace/circle_{n}_{z}.png')
    pg.evaluate("map.setBearing(40)"); pg.wait_for_timeout(300)
    pg.click('#bar .cpick.rng .cbtn'); pg.click("#bar .cpick.rng .cmenu div:text-is('40 mi')"); pg.wait_for_timeout(700)
    bx=pg.evaluate(BOX); ok(f'{n} heading-up (bearing 40) fit ok',inview(bx),{k:round(v,2) for k,v in bx.items()}); pg.evaluate("map.setBearing(0)"); pg.wait_for_timeout(500)
    z0=pg.evaluate("map.getZoom()"); pg.evaluate(f"updateMyMarker(35.85,{lon})"); pg.wait_for_timeout(400)
    f=pg.evaluate("()=>[rangeCircle.getLatLng().lat,map.getZoom()]"); ok(f'{n} circle follows position, no re-zoom on move',abs(f[0]-35.85)<1e-9 and f[1]==z0,[f,z0])
    # taps go through: rider marker inside circle opens popup; map point hit-test is not the circle
    pg.evaluate(f"()=>{{riders['qa-c']=L.marker([35.9,{lon}]).addTo(map).bindPopup('QA C')}}"); pg.wait_for_timeout(300)
    pt=pg.evaluate("()=>{const r=riders['qa-c']._icon.getBoundingClientRect();return [r.left+r.width/2,r.top+r.height/2]}")
    hit=pg.evaluate(f"document.elementFromPoint({pt[0]},{pt[1]})===riders['qa-c']._icon")
    pg.mouse.click(*pt); pg.wait_for_timeout(300); pop=pg.evaluate("riders['qa-c'].isPopupOpen()")
    mp=pg.evaluate("()=>{const c=map.latLngToContainerPoint(map.getCenter());const r=map.getContainer().getBoundingClientRect();const el=document.elementFromPoint(r.left+c.x+60,r.top+c.y+120);return el!==rangeCircle._path}")
    ok(f'{n} circle does not block taps (marker popup opens, map gets taps)',hit and pop and mp,[hit,pop,mp])
    ok(f'{n} no page errors',not [x for x in e if 'manifest.json?ping' not in x],e)
    b.close()
  f=[k for k,v in R if not v]; print(f'PASSED {len(R)-len(f)}/{len(R)}','FAILS',f)
