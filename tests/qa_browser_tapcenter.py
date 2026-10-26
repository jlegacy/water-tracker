"""Tapping a marker (self or another rider) centers the map on it, in North Up and Heading Up, at zoom 9 and 16.
Regression: leaflet-rotate popup autoPan panned the wrong way when rotated (jumped ~11 km at zoom 9)."""
import sys
from playwright.sync_api import sync_playwright
URL=sys.argv[1]; R=[]
def geo(lat,lon): return """(()=>{const mk=()=>({coords:{latitude:%f,longitude:%f,accuracy:5,heading:null,speed:null},timestamp:Date.now()});
const g={getCurrentPosition(ok){setTimeout(()=>ok(mk()),200)},watchPosition(ok){setTimeout(()=>ok(mk()),200);return 1},clearWatch(){}};
Object.defineProperty(navigator,'geolocation',{get:()=>g});})()"""%(lat,lon)
def ok(k,v,d=''): R.append(bool(v)); print(k,'PASS' if v else 'FAIL',d)
def join(b,kw,name,lat,lon,errs):
  c=b.new_context(**kw); c.route('**/*onrender.com*/**',lambda r:r.abort()); c.add_init_script(geo(lat,lon))
  pg=c.new_page(); pg.on('pageerror',lambda e:errs.append(str(e))); pg.goto(URL); pg.fill('#startName',name); pg.evaluate('startApp()')
  pg.wait_for_function("()=>ws&&ws.readyState===1&&myLatLng",timeout=15000); return c,pg
# marker's on-screen offset from map center (px); popup opens above, so offsets put it near edges where autoPan used to fire
OFFS=[(0,-200),(120,-180),(-120,160)]
PLACE="""([id,dx,dy,z])=>{map.setZoom(z,{animate:false});const s=map.getSize(),m=riders[id].getLatLng();
 const want=L.point(s.x/2+dx,s.y/2+dy);const at=map.latLngToContainerPoint(m);const c=L.point(s.x/2,s.y/2).add(at.subtract(want));map.setView(map.containerPointToLatLng(c),z,{animate:false}); // panBy is not rotation-aware
 const r=riders[id].getElement().getBoundingClientRect();const x=r.x+r.width/2,y=r.y+r.height/2;const e=document.elementFromPoint(x,y);
 return [x,y,!!e&&riders[id].getElement().contains(e)]}"""
CHK="""(id)=>{const s=map.getSize(),p=map.latLngToContainerPoint(riders[id].getLatLng());return [Math.round(p.x-s.x/2),Math.round(p.y-s.y/2),riders[id].isPopupOpen(),Math.round(map.getBearing())]}"""
with sync_playwright() as p:
  for n in sys.argv[2:] or ['chromium','webkit']:
    kw=dict(p.devices['iPhone 15']) if n=='webkit' else {'viewport':{'width':393,'height':852},'has_touch':True}; kw.pop('default_browser_type',None)
    b=getattr(p,n).launch(); errs=[]; OFF=0 if n=='chromium' else 5
    c1,v=join(b,kw,'Viewer '+n,35.807,-77.378+OFF,errs)
    c2,r=join(b,kw,'Other '+n,35.95,-77.15+OFF,errs); rid=r.evaluate('me')
    v.wait_for_function(f"()=>riders['{rid}']&&riders['{rid}'].getElement()",timeout=15000); v.wait_for_timeout(800)
    for hu in (False,True):
      v.evaluate(f"()=>{{headingMode='{'heading' if hu else 'north'}';lastHeading={'120' if hu else 'null'};applyBearing()}}")
      for z in (9,16):
        for who in ('self','other'):
          tapped=0
          for dx,dy in OFFS:
            v.evaluate("()=>{for(const k in riders)riders[k].closePopup&&riders[k].closePopup();map.closePopup();userMovedMap()}"); v.wait_for_timeout(400)
            idx=v.evaluate('me') if who=='self' else rid
            x,y,hit=v.evaluate(PLACE,[idx,dx,dy,z])
            if not hit: continue  # covered by app UI at this spot
            tapped+=1; v.touchscreen.tap(x,y); v.wait_for_timeout(900)
            ox,oy,pop,bear=v.evaluate(CHK,idx)
            ok(f"{n} {'HeadingUp' if hu else 'NorthUp'} z{z} tap {who} @({dx},{dy}) -> centered",abs(ox)<=3 and abs(oy)<=3 and pop and bear==(240 if hu else 0),[ox,oy,pop,bear])
          ok(f"{n} {'HU' if hu else 'NU'} z{z} {who}: at least one tappable spot",tapped>0)
    ok(f'{n} no page errors',not errs,errs); b.close()
print('ALL PASS' if all(R) else 'SOME FAIL')
