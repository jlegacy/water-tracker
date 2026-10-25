"""Rider picker enabled/disabled QA. Usage: python qa_browser_picker.py http://127.0.0.2:8811/"""
import sys
from playwright.sync_api import sync_playwright
URL=sys.argv[1]; R=[]
def geo(lat,lon): return """(()=>{window.__ll=[%f,%f];const mk=()=>({coords:{latitude:__ll[0],longitude:__ll[1],accuracy:5,heading:null,speed:null},timestamp:Date.now()});
const g={getCurrentPosition(ok){setTimeout(()=>ok(mk()),200)},watchPosition(ok){setTimeout(()=>ok(mk()),200);return 1},clearWatch(){}};
Object.defineProperty(navigator,'geolocation',{get:()=>g});})()"""%(lat,lon)
def ok(k,v,d=''): R.append((k,bool(v))); print(k,'PASS' if v else 'FAIL',d)
DIS="()=>[document.getElementById('riderBtn').disabled,document.getElementById('riderList').disabled,document.getElementById('riderMenu').classList.contains('open')]"
def join(b,kw,name,lat,lon,errs):
  c=b.new_context(**kw); c.route('**/*onrender.com*/**',lambda r:r.abort()); c.add_init_script(geo(lat,lon))
  pg=c.new_page(); pg.on('pageerror',lambda e:errs.append(str(e))); pg.goto(URL); pg.fill('#startName',name); pg.evaluate('startApp()')
  pg.wait_for_function("()=>ws&&ws.readyState===1&&myLatLng",timeout=15000); return c,pg
def wait_state(pg,want,ms=8000):
  try: pg.wait_for_function(f"()=>document.getElementById('riderBtn').disabled==={'true' if want else 'false'}",timeout=ms)
  except Exception: pass
  return pg.evaluate(DIS)
with sync_playwright() as p:
  for n in sys.argv[2:] or ['chromium','webkit']:
    kw=dict(p.devices['iPhone 15']) if n=='webkit' else {}; kw.pop('default_browser_type',None)
    b=getattr(p,n).launch(); errs=[]
    OFF={'chromium':0,'webkit':5,'firefox':10}.get(n,15)  # separate areas so one browser's riders never reach the next
    c1,v=join(b,kw,'Viewer '+n,35.807,-77.378+OFF,errs); v.wait_for_timeout(1500)
    s=v.evaluate(DIS); ok(f'{n} empty -> disabled',s==[True,True,False],s)
    def rider(lat=35.81,lon=None):
      lon=-77.38+OFF if lon is None else lon
      c,pg=join(b,kw,'Rider '+n,lat,lon,errs); rid=pg.evaluate('me'); return c,pg,rid
    c2,r,rid=rider(); s=wait_state(v,False); v.evaluate("toggleRiderMenu()"); op=v.evaluate(DIS)[2]; v.evaluate("document.getElementById('riderMenu').classList.remove('open')")
    ok(f'{n} rider joins -> enabled, menu opens',s[:2]==[False,False] and op,s)
    # 1) explicit leave
    v.evaluate("toggleRiderMenu()"); r.evaluate("ws.send(JSON.stringify({type:'leave'}))")
    s=wait_state(v,True); ok(f'{n} explicit leave -> disabled, menu closed',s==[True,True,False] and rid not in v.evaluate('Object.keys(positions)'),s)
    c2.close()
    # 2) out-of-range hysteresis leave (rider moves ~35 mi away; viewer range 25, hide at 27)
    c2,r,rid=rider(); s=wait_state(v,False); ok(f'{n} rider back -> enabled',s[:2]==[False,False],s)
    far=f"[{35.807+0.51},{-77.378+OFF}]"; r.evaluate(f"()=>{{__ll={far};ws.send(JSON.stringify({{type:'pos',lat:__ll[0],lon:__ll[1],ts:Date.now()}}))}}")
    s=wait_state(v,True); ok(f'{n} out-of-range leave -> disabled',s==[True,True,False],s)
    r.evaluate("ws.send(JSON.stringify({type:'leave'}))"); c2.close()
    # 3) stale cleanup (silent > 30 min): stop rider sending, age it on the viewer, run the prune pass
    c2,r,rid=rider(); s=wait_state(v,False); ok(f'{n} rider back again -> enabled',s[:2]==[False,False],s)
    r.evaluate("ws.onclose=null; ws.send=()=>{}; ws.close()"); v.wait_for_timeout(500)
    v.evaluate(f"()=>{{if(lastSeen['{rid}']!=null) lastSeen['{rid}']-=31*60000; pruneRiders()}}")
    s=v.evaluate(DIS); ok(f'{n} stale cleanup -> disabled',s==[True,True,False] and rid not in v.evaluate('Object.keys(positions)'),s)
    # 4) leftover position with no marker is still cleared by remove()
    v.evaluate(f"()=>{{positions['ghost']={{lat:35.81,lon:{-77.38+OFF},name:'Ghost'}};lastListKey=null;updateRiderList()}}")
    a=v.evaluate(DIS)[0]; v.evaluate("remove('ghost')"); s=v.evaluate(DIS)
    ok(f'{n} marker-less entry removed -> disabled',a is False and s[0] is True,[a,s])
    ok(f'{n} no page errors',not errs,errs)
    v.evaluate("ws.send(JSON.stringify({type:'leave'}))"); c2.close(); c1.close(); b.close()
  f=[k for k,v in R if not v]; print(f'PASSED {len(R)-len(f)}/{len(R)}','FAILS',f)
