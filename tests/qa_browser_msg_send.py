"""Send/All buttons disabled when the message box is empty/whitespace; enabled live on typing/paste; re-disabled after send; send functions ignore empty text."""
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
ST="()=>[document.getElementById('sendBtn').disabled,document.getElementById('allBtn').disabled]"
SPY="()=>{if(!ws.__spy){const o=ws.send.bind(ws);ws.__n=0;ws.send=d=>{try{const t=JSON.parse(d).type;if(t==='msg'||t==='broadcast')ws.__n++}catch(e){};return o(d)};ws.__spy=1}return ws.__n}"
with sync_playwright() as p:
  for n in sys.argv[2:] or ['chromium','webkit']:
    kw=dict(p.devices['iPhone 15']) if n=='webkit' else {'viewport':{'width':393,'height':852},'has_touch':True}; kw.pop('default_browser_type',None)
    b=getattr(p,n).launch(); errs=[]; O=0 if n=='chromium' else 3
    c1,v=join(b,kw,'MsgA '+n,35.807,-77.378+O,errs); c2,r=join(b,kw,'MsgB '+n,35.81,-77.37+O,errs); rid=r.evaluate('me')
    v.wait_for_function("()=>getComputedStyle(document.getElementById('sendBtn')).display!=='none'",timeout=15000)
    v.evaluate(SPY)
    ok(f'{n} empty -> both disabled',v.evaluate(ST)==[True,True],v.evaluate(ST))
    v.click('#msgText'); v.keyboard.type('   '); v.wait_for_timeout(100)
    ok(f'{n} whitespace -> disabled',v.evaluate(ST)==[True,True],v.evaluate(ST))
    v.keyboard.type('hi'); v.wait_for_timeout(100)
    ok(f'{n} typing -> enabled',v.evaluate(ST)==[False,False],v.evaluate(ST))
    v.fill('#msgText',''); v.wait_for_timeout(100)
    ok(f'{n} cleared -> disabled',v.evaluate(ST)==[True,True],v.evaluate(ST))
    v.evaluate("()=>{const t=document.getElementById('msgText');t.value='pasted';t.dispatchEvent(new Event('paste',{bubbles:true}))}"); v.wait_for_timeout(100)
    ok(f'{n} paste -> enabled',v.evaluate(ST)==[False,False],v.evaluate(ST))
    v.click('#allBtn'); v.wait_for_timeout(600)
    ok(f'{n} broadcast sent, box cleared, re-disabled',v.evaluate(SPY)==1 and v.input_value('#msgText')=='' and v.evaluate(ST)==[True,True],[v.evaluate(SPY),v.evaluate(ST)])
    v.evaluate(f"()=>{{const s=document.getElementById('riderList');s.value='{rid}';onRiderSelect()}}"); v.wait_for_timeout(300)
    v.click('#msgText'); v.keyboard.type('dm'); v.wait_for_timeout(100)
    ok(f'{n} DM typing -> enabled',v.evaluate(ST)[0]==False,v.evaluate(ST))
    v.click('#sendBtn'); v.wait_for_timeout(600)
    ok(f'{n} DM sent, re-disabled',v.evaluate(SPY)==2 and v.evaluate(ST)==[True,True],[v.evaluate(SPY),v.evaluate(ST)])
    v.evaluate("()=>{document.getElementById('msgText').value='   ';sendMessage();broadcastMessage();document.getElementById('msgText').value='';sendMessage();broadcastMessage()}")
    ok(f'{n} guards: empty/whitespace calls send nothing',v.evaluate(SPY)==2,v.evaluate(SPY))
    ok(f'{n} no page errors',not errs,errs); b.close()
print('ALL PASS' if all(R) else 'SOME FAIL')
