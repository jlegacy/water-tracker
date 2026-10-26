import sys
from playwright.sync_api import sync_playwright
INIT="""(()=>{const mk=()=>({coords:{latitude:35.807,longitude:-77.378+%s,accuracy:5,heading:null,speed:null},timestamp:Date.now()});
const g={getCurrentPosition(ok){setTimeout(()=>ok(mk()),200)},watchPosition(ok){setTimeout(()=>ok(mk()),200);return 1},clearWatch(){}};
Object.defineProperty(navigator,'geolocation',{get:()=>g});})()"""
PROPS=['fontFamily','fontSize','fontWeight','height','paddingTop','paddingBottom','borderTopWidth','borderTopColor','borderTopLeftRadius','backgroundColor','color','lineHeight']
CMP="""()=>{const P=%s;const a=getComputedStyle(document.getElementById('riderBtn')),b=getComputedStyle(document.querySelector('#bar .cpick.rng .cbtn'));
const ca=getComputedStyle(document.querySelector('#riderBtn .car')),cb=getComputedStyle(document.querySelector('#bar .cpick.rng .cbtn .car'));
const ma=getComputedStyle(document.getElementById('riderMenu')),mb=getComputedStyle(document.querySelector('#bar .cpick.rng .cmenu'));
const diff=P.filter(k=>a[k]!==b[k]).map(k=>k+':'+a[k]+'≠'+b[k]);
['fontSize','opacity'].forEach(k=>{if(ca[k]!==cb[k])diff.push('car.'+k)});
['backgroundColor','borderTopLeftRadius','borderTopColor','boxShadow'].forEach(k=>{if(ma[k]!==mb[k])diff.push('menu.'+k)});
return [diff,document.querySelector('#riderBtn .car').textContent===document.querySelector('#bar .cpick.rng .car').textContent]}"""%PROPS
R=[]
def ok(k,v,d=''): R.append((k,bool(v))); print(k,'PASS' if v else 'FAIL',d)
with sync_playwright() as p:
  for i,n in enumerate(('chromium','webkit')):
    kw=dict(p.devices['iPhone 15']) if n=='webkit' else {'viewport':{'width':393,'height':852}}; kw.pop('default_browser_type',None)
    b=getattr(p,n).launch(); c=b.new_context(**kw); c.route('**/*onrender.com*/**',lambda r:r.abort()); c.add_init_script(INIT%(i*5))
    pg=c.new_page(); e=[]; pg.on('pageerror',lambda x:e.append(str(x)))
    pg.goto(sys.argv[1]); pg.wait_for_timeout(800)
    js=pg.evaluate("()=>[!!document.querySelector('#nameScreen .cpick.rng-start .cbtn'),getComputedStyle(document.getElementById('startRange')).display,document.querySelector('#nameScreen .cpick.rng-start .lbl').textContent]")
    ok(f'{n} join range uses custom picker',js[0] and js[1]=='none' and js[2]=='5 mi',js)
    pg.click('#nameScreen .cpick.rng-start .cbtn'); pg.screenshot(path=f'/workspace/range_{n}_join_open.png'); pg.click("#nameScreen .cpick.rng-start .cmenu div:text-is('30 mi')")
    pg.fill('#startName','QA Style '+n); pg.evaluate('startApp()'); pg.wait_for_timeout(1500)
    # give the riders list one fake rider so it's enabled (same look as in use)
    pg.evaluate(f"()=>{{positions['qa-s']={{lat:35.81,lon:{-77.38+i*5},name:'Sample Rider'}};lastSeen['qa-s']=Date.now();riders['qa-s']=L.marker([35.81,{-77.38+i*5}]).addTo(map);lastListKey=null;updateRiderList()}}")
    d=pg.evaluate(CMP); ok(f'{n} computed styles match riders list',not d[0] and d[1],d)
    lab=pg.evaluate("document.querySelector('#bar .cpick.rng .lbl').textContent"); ok(f'{n} map picker shows join choice',lab=='30 mi',lab)
    fit=pg.evaluate("()=>[document.documentElement.scrollWidth<=innerWidth,[...document.querySelectorAll('#bar .row > *')].filter(x=>x.offsetParent).every(x=>{const r=x.getBoundingClientRect();return r.right<=innerWidth+.5&&r.left>=-.5})]")
    ok(f'{n} fits {pg.viewport_size["width"]}px, no h-scroll',all(fit),fit)
    pg.screenshot(path=f'/workspace/range_{n}_closed.png')
    pg.click('#bar .cpick.rng .cbtn'); pg.wait_for_timeout(200)
    st=pg.evaluate("()=>{const m=document.querySelector('#bar .cpick.rng .cmenu');const r=m.getBoundingClientRect();return [m.classList.contains('open'),r.right<=innerWidth+.5,r.left>=-.5,[...m.children].map(x=>x.textContent).join(','),m.querySelector('.sel').textContent]}")
    ok(f'{n} range menu opens on-screen with 25..50, current selected',st[0] and st[1] and st[2] and st[3]=='1 mi,5 mi,10 mi,15 mi,25 mi,30 mi,35 mi,40 mi,45 mi,50 mi' and st[4]=='30 mi',st)
    pg.screenshot(path=f'/workspace/range_{n}_range_open.png')
    pg.click("#bar .cpick.rng .cmenu div:text-is('45 mi')"); pg.wait_for_timeout(600)
    lv=pg.evaluate("()=>[myRange,localStorage.getItem('trackerRange'),document.getElementById('status').textContent,document.querySelector('#bar .cpick.rng .cmenu').classList.contains('open')]")
    ok(f'{n} pick 45 -> live + persisted, menu closes',lv[0]==45 and lv[1]=='45' and lv[2].endswith('45 mi') and not lv[3],lv)
    pg.click('#riderBtn'); pg.wait_for_timeout(200); x=pg.evaluate("()=>[document.getElementById('riderMenu').classList.contains('open'),document.querySelector('#bar .cpick.rng .cmenu').classList.contains('open')]")
    pg.screenshot(path=f'/workspace/range_{n}_riders_open.png')
    pg.click('#bar .cpick.rng .cbtn'); pg.wait_for_timeout(200); y=pg.evaluate("()=>[document.getElementById('riderMenu').classList.contains('open'),document.querySelector('#bar .cpick.rng .cmenu').classList.contains('open')]")
    pg.mouse.click(200,700); pg.wait_for_timeout(200); z=pg.evaluate("()=>document.querySelectorAll('.cmenu.open,#riderMenu.open').length")
    ok(f'{n} only one menu open at a time; outside tap closes',x==[True,False] and y==[False,True] and z==0,[x,y,z])
    pg.reload(); pg.wait_for_timeout(1200); pr=pg.evaluate("()=>[document.querySelector('#nameScreen .cpick.rng-start .lbl').textContent,document.querySelector('#bar .cpick.rng .lbl').textContent]")
    ok(f'{n} persists after reload',pr==['45 mi','45 mi'],pr)
    ok(f'{n} no page errors',not [x for x in e if 'manifest.json?ping' not in x],e)
    b.close()
  f=[k for k,v in R if not v]; print(f'PASSED {len(R)-len(f)}/{len(R)}','FAILS',f)
