"""Rider list status filter chips QA. Usage: python qa_browser_rider_filter.py URL"""
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
return [...document.querySelectorAll('#riderMenu div')].slice(1).map(d=>[d.querySelector('.lbl').textContent,(d.querySelector('.rtag')||{}).textContent||'',(d.querySelector('.rseen')||{}).textContent||'']).concat([[...document.getElementById('riderList').options].slice(1).map(o=>o.textContent)]);}"""
CH="()=>[...document.querySelectorAll('#rfBar button')].map(b=>[b.dataset.f,b.querySelector('b').textContent,b.classList.contains('on'),b.classList.contains('zero')])"
ROWS="()=>[...document.querySelectorAll('#riderMenu > div')].slice(1).map(d=>d.querySelector('.lbl').textContent.split(' (')[0])"
with sync_playwright() as p:
  for n in sys.argv[2:] or ['chromium','webkit']:
    b=getattr(p,n).launch(); c=b.new_context(viewport={'width':375,'height':740}); c.route('**/*onrender.com*/**',lambda r:r.abort()); c.add_init_script(GEO)
    errs=[]; pg=c.new_page(); pg.on('pageerror',lambda e:errs.append(str(e))); pg.goto(URL); pg.fill('#startName','Lead '+n); pg.evaluate('startApp()')
    pg.wait_for_function("()=>ws&&ws.readyState===1&&myLatLng",timeout=15000)
    pg.evaluate("()=>{ws.onmessage=null;return 1}")
    # isolate from riders left on the shared test server by earlier runs (snapshot may land before onmessage=null)
    pg.wait_for_timeout(500)
    pg.evaluate("()=>{const purge=()=>{let ch=false;for(const k in positions) if(k!==me&&!'abcd'.includes(k)){delete positions[k];ch=true;} if(ch){lastListKey=null;updateRiderList();}};purge();setInterval(purge,50);}")
    pg.evaluate("""()=>{const n=Date.now();
positions['a']={lat:35.808,lon:-60.0,name:'Near'};lastSeen['a']=n-3000;
positions['b']={lat:35.9,lon:-60.0,name:'Far'};lastSeen['b']=n-12000;
positions['c']={lat:35.85,lon:-60.0,name:'Quiet',stale:true};lastSeen['c']=n-4*60000;
lastListKey=null;updateRiderList();}""")
    pg.wait_for_function("()=>document.querySelectorAll('#rfBar button').length===4")
    ok(f'{n} old Riders dropdown button removed',pg.evaluate("()=>!document.getElementById('riderBtn')&&!document.getElementById('riderRow')"))
    ok(f'{n} no chips inside menu',pg.evaluate("()=>!document.querySelector('#riderMenu nav, #riderMenu .rfbar')"))
    pg.wait_for_timeout(400)
    bv=pg.evaluate("()=>{const b=document.getElementById('rfBar').getBoundingClientRect(),m=document.getElementById('msgBox').getBoundingClientRect(),mm=document.getElementById('map').getBoundingClientRect();return [b.height>0&&b.height<=30&&b.top>=m.bottom-1&&b.bottom<=mm.top+1&&!document.getElementById('riderMenu').classList.contains('open'),b.top,b.bottom,m.bottom,mm.top]}")
    ok(f'{n} bar visible below msg row with menu closed, compact',bv[0],bv)
    ch=pg.evaluate(CH)
    ok(f'{n} counts All3 Moving2 Quiet1 SOS0',[x[1] for x in ch]==['3','2','1','0'],ch)
    ok(f'{n} All active, SOS dimmed',ch[0][2] and ch[3][3] and not ch[1][3],ch)
    pg.click('#rfBar button[data-f=moving]'); r=pg.evaluate(ROWS)
    ok(f'{n} Moving filter',r==['Near','Far'] and pg.evaluate("()=>document.getElementById('riderMenu').classList.contains('open')"),r)
    ok(f'{n} Moving chip active',pg.evaluate(CH)[1][2])
    pg.click('#rfBar button[data-f=moving]'); r=pg.evaluate(ROWS)
    ok(f'{n} tap again resets',r==['Quiet','Near','Far'] and pg.evaluate(CH)[0][2],r)
    pg.click('#rfBar button[data-f=quiet]'); ok(f'{n} Quiet filter',pg.evaluate(ROWS)==['Quiet'])
    pg.evaluate("()=>{positions['d']={lat:36.0,lon:-60.0,name:'Help',sos:true,stale:true};lastSeen['d']=Date.now()-60000;updateRiderList();}")
    ch=pg.evaluate(CH); ok(f'{n} counts live-update on rider change',[x[1] for x in ch]==['4','2','1','1'] and not ch[3][3],ch)
    pg.click('#rfBar button[data-f=sos]'); ok(f'{n} SOS filter',pg.evaluate(ROWS)==['Help'])
    pg.click('#rfBar button[data-f=all]'); ok(f'{n} All resets',pg.evaluate(ROWS)==['Help','Quiet','Near','Far'])
    w=pg.evaluate("()=>{const r=document.querySelector('#rfBar').getBoundingClientRect();return r.right<=innerWidth+1}")
    ok(f'{n} fits 375px width',w)
    pg.click('#rfBar button[data-f=quiet]'); pg.click('#riderMenu > div:nth-of-type(2)')
    ok(f'{n} selecting filtered row selects rider',pg.evaluate("()=>document.getElementById('riderList').value")=='c')
    ok(f'{n} native select keeps all riders',pg.evaluate("()=>document.getElementById('riderList').options.length")==5)
    ok(f'{n} no page errors',not errs,errs); b.close()
  f=[k for k,v in R if not v]; print(f'PASSED {len(R)-len(f)}/{len(R)}','FAILS',f)
