"""Rider dropdown status labels + sort QA. Usage: python qa_browser_rider_status.py URL"""
import sys
from playwright.sync_api import sync_playwright
URL=sys.argv[1]; R=[]
GEO="""(()=>{const mk=()=>({coords:{latitude:35.807,longitude:-60.0,accuracy:5,heading:null,speed:null},timestamp:Date.now()});
const g={getCurrentPosition(ok){setTimeout(()=>ok(mk()),200)},watchPosition(ok){setTimeout(()=>ok(mk()),200);return 1},clearWatch(){}};
Object.defineProperty(navigator,'geolocation',{get:()=>g});})()"""
def ok(k,v,d=''): R.append((k,bool(v))); print(k,'PASS' if v else 'FAIL',d)
SETUP="""()=>{const n=Date.now();
positions['a']={lat:35.808,lon:-60.0,name:'Near'};lastSeen['a']=n-3000;
positions['b']={lat:35.9,lon:-60.0,name:'Far'};lastSeen['b']=n-12000;
positions['c']={lat:35.85,lon:-60.0,name:'Quiet',stale:true};lastSeen['c']=n-4*60000;
positions['d']={lat:36.0,lon:-60.0,name:'Help',sos:true,stale:true};lastSeen['d']=n-2*60000;
lastListKey=null;updateRiderList();renderRiderPicker();
return [...document.querySelectorAll('#riderMenu > div')].slice(1).map(d=>[d.querySelector('.lbl').textContent,(d.querySelector('.rtag')||{}).textContent||'',(d.querySelector('.rseen')||{}).textContent||'']).concat([[...document.getElementById('riderList').options].slice(1).map(o=>o.textContent)]);}"""
with sync_playwright() as p:
  for n in sys.argv[2:] or ['chromium','webkit']:
    b=getattr(p,n).launch(); c=b.new_context(); c.route('**/*onrender.com*/**',lambda r:r.abort()); c.add_init_script(GEO)
    errs=[]; pg=c.new_page(); pg.on('pageerror',lambda e:errs.append(str(e))); pg.goto(URL); pg.fill('#startName','Lead '+n); pg.evaluate('startApp()')
    pg.wait_for_function("()=>ws&&ws.readyState===1&&myLatLng",timeout=15000)
    ws=pg.evaluate("()=>{ws.onmessage=null;return 1}")
    rows=pg.evaluate(SETUP); opts=rows.pop()
    names=[r[0].split(' (')[0] for r in rows]
    ok(f'{n} sort SOS, quiet, then distance',names==['Help','Quiet','Near','Far'],names)
    ok(f'{n} SOS tag + last-seen',rows[0][1]=='SOS' and rows[0][2]=='2m ago',rows[0])
    ok(f'{n} Quiet 4m tag',rows[1][1]=='Quiet 4m' and rows[1][2]=='4m ago',rows[1])
    ok(f'{n} fresh rows: no tag, now/12s',rows[2][1:]==['','now'] and rows[3][1:]==['','12s'],rows[2:])
    ok(f'{n} select text fallback',opts[0].startswith('SOS · Help') and opts[1].startswith('Quiet 4m · Quiet'),opts)
    ok(f'{n} no page errors',not errs,errs); b.close()
  f=[k for k,v in R if not v]; print(f'PASSED {len(R)-len(f)}/{len(R)}','FAILS',f)
