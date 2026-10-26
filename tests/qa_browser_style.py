import sys
from playwright.sync_api import sync_playwright
INIT="""(()=>{const mk=()=>({coords:{latitude:%s,longitude:%s,accuracy:5,heading:null,speed:null},timestamp:Date.now()});
const g={getCurrentPosition(ok){setTimeout(()=>ok(mk()),200)},watchPosition(ok){setTimeout(()=>ok(mk()),200);return 1},clearWatch(){}};
Object.defineProperty(navigator,'geolocation',{get:()=>g});})()"""
R=[]
def ok(k,v,d=''): R.append((k,bool(v))); print(k,'PASS' if v else 'FAIL',d)
MARK="""(id)=>{const el=riders[id]&&riders[id]._icon;if(!el)return null;const bgs=[...el.querySelectorAll('*')].map(x=>getComputedStyle(x).backgroundColor);const bb=[...el.querySelectorAll('*')].map(x=>getComputedStyle(x).borderBottomColor);return {txt:el.textContent.replace(/\\s+/g,''),bgs,bb}}"""
FIT="()=>[document.documentElement.scrollWidth<=innerWidth,[...document.querySelectorAll('#bar .row > *')].filter(x=>x.offsetParent).every(x=>{const r=x.getBoundingClientRect();return r.right<=innerWidth+.5&&r.left>=-.5})]"
with sync_playwright() as p:
  for k,n in enumerate(('chromium','webkit')):
    lon=-77.378+k*5
    kw=dict(p.devices['iPhone 15']) if n=='webkit' else {'viewport':{'width':393,'height':852}}; kw.pop('default_browser_type',None)
    b=getattr(p,n).launch(); E=[]
    def mk(lat):
      c=b.new_context(**kw); c.route('**/*onrender.com*/**',lambda r:r.abort()); c.add_init_script(INIT%(lat,lon))
      pg=c.new_page(); pg.on('pageerror',lambda x:E.append(str(x))); return pg
    A=mk(35.807); B=mk(35.82)
    A.goto(sys.argv[1]); A.wait_for_timeout(800)
    A.click('#styleOpenJoin'); A.wait_for_timeout(200)
    vis=A.evaluate("()=>{const p=document.getElementById('stylePanel');const r=p.querySelector('.box').getBoundingClientRect();return [p.classList.contains('open'),r.left>=0&&r.right<=innerWidth,document.querySelectorAll('#styleColors .sw').length,document.querySelectorAll('#styleIcons .ic').length,[...document.querySelectorAll('#styleColors .sw')].map(x=>getComputedStyle(x).backgroundColor)]}")
    bad=[c for c in vis[4] if c in ('rgb(220, 38, 38)','rgb(139, 92, 246)','rgb(239, 68, 68)')]
    ok(f'{n} join picker opens on-screen, 10 colors / 9 icons, no SOS red/leader purple',vis[0] and vis[1] and vis[2]==10 and vis[3]==9 and not bad,vis[:4])
    A.click("#styleColors .sw[data-c='orange']"); A.click("#styleIcons .ic[data-i='shark']"); A.screenshot(path=f'/workspace/style_{n}_picker.png')
    A.click('#stylePanel .done')
    A.fill('#startName','QA Styler '+n); A.evaluate('startApp()'); A.wait_for_timeout(1500)
    me=A.evaluate("()=>{const el=riders[me]._icon;return [el.textContent.replace(/\\s+/g,''),[...el.querySelectorAll('*')].map(x=>getComputedStyle(x).backgroundColor),JSON.parse(localStorage.getItem('trackerStyle'))]}")
    ok(f'{n} own marker shows chosen color/icon + saved',me[0]=='🦈' and 'rgb(234, 88, 12)' in me[1] and me[2]=={'c':'orange','i':'shark'},me)
    B.goto(sys.argv[1]); B.wait_for_timeout(800); B.fill('#startName','QA Watch '+n); B.evaluate('startApp()'); B.wait_for_timeout(3000)
    aid=A.evaluate('me')
    m=B.evaluate(MARK,aid); ok(f'{n} other rider sees orange shark marker',m and m['txt']=='🦈' and 'rgb(234, 88, 12)' in m['bgs'],m)
    B.click('#riderBtn'); B.wait_for_timeout(200)
    row=B.evaluate("()=>{const d=[...document.querySelectorAll('#riderMenu div')].find(x=>x.textContent.includes('QA Styler'));return d&&[d.querySelector('.rico')&&d.querySelector('.rico').textContent,getComputedStyle(d.querySelector('.rdot')).backgroundColor]}")
    ok(f'{n} riders drop-down shows icon + color dot',row==['🦈','rgb(234, 88, 12)'],row)
    B.screenshot(path=f'/workspace/style_{n}_observer_dropdown.png'); B.mouse.click(200,700)
    # live change from the map screen via 🎨 button
    fit=A.evaluate(FIT); ok(f'{n} top bar fits 393px with 🎨 button, no h-scroll',all(fit) and A.is_visible('#lookBtn'),fit)
    A.click('#lookBtn'); A.click("#styleColors .sw[data-c='green']"); A.click("#styleIcons .ic[data-i='anchor']"); A.click('#stylePanel .done'); A.wait_for_timeout(2500)
    m=B.evaluate(MARK,aid); ok(f'{n} live change propagates (green anchor)',m and m['txt']=='⚓' and 'rgb(22, 163, 74)' in m['bgs'],m)
    B.screenshot(path=f'/workspace/style_{n}_observer_map.png')
    # leader override: purple + star, custom icon hidden
    A.click('#leaderBtn'); A.wait_for_timeout(2500)
    m=B.evaluate(MARK,aid); ok(f'{n} leader overrides style (purple + star)',m and '★' in m['txt'] and '⚓' not in m['txt'] and 'rgb(139, 92, 246)' in m['bgs'],m)
    A.click('#leaderBtn'); A.wait_for_timeout(1500)
    # SOS override
    A.click('#sosBtn')
    A.wait_for_timeout(2500)
    m=B.evaluate(MARK,aid); ok(f'{n} SOS overrides style (🆘)',m and '🆘' in m['txt'] and '⚓' not in m['txt'],m)
    B.screenshot(path=f'/workspace/style_{n}_observer_sos.png')
    A.click('#sosBtn')
    A.wait_for_timeout(1500)
    # stale still greys out
    B.evaluate(f"()=>{{positions['{aid}'].stale=true;setRiderStale('{aid}',true)}}")
    m=B.evaluate(MARK,aid); ok(f'{n} stale styling still applies',m and 'rgb(156, 163, 175)' in m['bgs'],m)
    # persists after reload
    A.reload(); A.wait_for_timeout(1200); pr=A.evaluate("()=>[myStyle.c,myStyle.i,document.getElementById('styleJoinPrev').textContent]")
    ok(f'{n} style persists after reload',pr==['green','anchor','⚓'],pr)
    ok(f'{n} no page errors',not [x for x in E if 'manifest.json?ping' not in x],E)
    for pg in (A,B):
      try: pg.evaluate("ws&&ws.send(JSON.stringify({type:'leave'}))")
      except Exception: pass
    b.close()
  f=[k for k,v in R if not v]; print(f'PASSED {len(R)-len(f)}/{len(R)}','FAILS',f)
