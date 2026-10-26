# TEMP-DELETE-TRAILS test: remove together with the button
import sys
from playwright.sync_api import sync_playwright
INIT="""(()=>{const mk=()=>({coords:{latitude:35.807,longitude:-77.378,accuracy:5,heading:null,speed:null},timestamp:Date.now()});
const g={getCurrentPosition(ok){setTimeout(()=>ok(mk()),200)},watchPosition(ok){setTimeout(()=>ok(mk()),200);return 1},clearWatch(){}};
Object.defineProperty(navigator,'geolocation',{get:()=>g});})()"""
R=[]
def ok(k,v,d=''): R.append(bool(v)); print(k,'PASS' if v else 'FAIL',d)
SEED="""async()=>{const db=await openTrailDb();await new Promise(r=>{const tx=db.transaction(TRAIL_DB_STORE,'readwrite');tx.objectStore(TRAIL_DB_STORE).put({id:'qa1',startedAt:Date.now()-6e5,endedAt:Date.now(),points:[{lat:35.8,lon:-77.37,t:1},{lat:35.81,lon:-77.38,t:2}]});tx.oncomplete=r});
localStorage.setItem(RIDE_DRAFT_KEY,JSON.stringify({id:'d',points:[]}));breadcrumb=[{lat:35.80,lon:-77.37,t:Date.now()-9e4},{lat:35.805,lon:-77.375,t:Date.now()-6e4},{lat:35.807,lon:-77.378,t:Date.now()}];
breadcrumbLine=breadcrumbLine||L.polyline([[35.8,-77.37],[35.807,-77.378]]).addTo(map);pastOverlayLine=L.polyline([[35.8,-77.37],[35.81,-77.38]]).addTo(map);}"""
ST="""async()=>{const db=await openTrailDb();const n=await new Promise(r=>{const q=db.transaction(TRAIL_DB_STORE).objectStore(TRAIL_DB_STORE).count();q.onsuccess=()=>r(q.result)});
return {idb:n,draft:localStorage.getItem(RIDE_DRAFT_KEY),bc:breadcrumb.length,line:!!breadcrumbLine,past:!!pastOverlayLine,polys:document.querySelectorAll('.leaflet-overlay-pane path.leaflet-interactive, .leaflet-overlay-pane path').length,toast:document.getElementById('rampToast').style.display==='block'?document.getElementById('rampToast').textContent:''}}"""
with sync_playwright() as p:
  for n in ('chromium','webkit'):
    kw=dict(p.devices['iPhone 15']) if n=='webkit' else {'viewport':{'width':393,'height':852}}; kw.pop('default_browser_type',None)
    b=getattr(p,n).launch(); c=b.new_context(**kw); c.route('**/*onrender.com*/**',lambda r:r.abort()); c.add_init_script(INIT)
    pg=c.new_page(); E=[]; pg.on('pageerror',lambda x:E.append(str(x))); W=[]
    pg.goto(sys.argv[1]); pg.wait_for_timeout(800); pg.fill('#startName','QA Del '+n); pg.evaluate('startApp()'); pg.wait_for_timeout(1500)
    sent=[]; pg.evaluate("()=>{const s=ws.send.bind(ws);window._sent=[];ws.send=m=>{_sent.push(m);s(m)}}")
    pg.evaluate(SEED); s0=pg.evaluate(ST); ok(f'{n} seeded',s0['idb']>=1 and s0['draft'] and s0['bc']==3 and s0['line'] and s0['past'],s0)
    pg.click('#lookBtn'); pg.wait_for_timeout(200); ok(f'{n} button visible in marker panel',pg.is_visible('#tempDeleteTrailsBtn'))
    pg.once('dialog',lambda d:(W.append(d.message),d.dismiss())); pg.click('#tempDeleteTrailsBtn'); pg.wait_for_timeout(500)
    s1=pg.evaluate(ST); ok(f'{n} cancel keeps everything',W and s1['idb']==s0['idb'] and s1['draft'] and s1['bc']==3,s1)
    pg.once('dialog',lambda d:d.accept()); pg.click('#tempDeleteTrailsBtn'); pg.wait_for_timeout(700)
    s2=pg.evaluate(ST); ok(f'{n} confirm wipes IDB, draft, breadcrumb, polylines + toast',s2['idb']==0 and not s2['draft'] and s2['bc']==0 and not s2['line'] and not s2['past'] and 'deleted' in s2['toast'],s2)
    snt=pg.evaluate("()=>_sent.filter(m=>/trail|delete/i.test(m)&&!/\"type\":\"pos\"/.test(m))"); ok(f'{n} nothing trail-related sent to server',not snt,snt)
    ok(f'{n} no page errors',not E,E); b.close()
print('ALL PASS' if all(R) else 'SOME FAIL')
