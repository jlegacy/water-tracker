"""Shake-to-undo fix: after join, inputs are blurred and replaced (no undo history); historyUndo is refused."""
import sys
from playwright.sync_api import sync_playwright
INIT="""(()=>{const mk=()=>({coords:{latitude:35.807,longitude:-77.378,accuracy:5,heading:null,speed:null},timestamp:Date.now()});
const g={getCurrentPosition(ok){setTimeout(()=>ok(mk()),200)},watchPosition(ok){setTimeout(()=>ok(mk()),200);return 1},clearWatch(){}};
Object.defineProperty(navigator,'geolocation',{get:()=>g});})()"""
R=[]
def ok(k,v,d=''): R.append(bool(v)); print(k,'PASS' if v else 'FAIL',d)
with sync_playwright() as p:
  for n in ('webkit','chromium'):
    kw=dict(p.devices['iPhone 15']) if n=='webkit' else {'viewport':{'width':393,'height':852}}; kw.pop('default_browser_type',None)
    b=getattr(p,n).launch(); c=b.new_context(**kw); c.route('**/*onrender.com*/**',lambda r:r.abort()); c.add_init_script(INIT)
    pg=c.new_page(); E=[]; pg.on('pageerror',lambda x:E.append(str(x)))
    pg.goto(sys.argv[1]); pg.wait_for_timeout(800)
    pg.evaluate("()=>{window._old=document.getElementById('startName')}")
    pg.click('#startName'); pg.keyboard.type('QA Undo '+n)
    # control: before the fix runs, the typing IS undoable in this engine
    canUndo=pg.evaluate("()=>{const i=document.getElementById('startName');i.focus();const v=i.value;const r=document.execCommand('undo');const u=i.value!==v;document.execCommand('redo');if(i.value!==v)i.value=v;return u}")
    pg.click('#nameScreen button[onclick="startApp()"]'); pg.wait_for_timeout(2500)
    st=pg.evaluate("""()=>{const i=document.getElementById('startName');const a=document.activeElement;
      return {replaced:i!==window._old,val:i.value,active:a?a.tagName:'',myName}}""")
    ok(f'{n} after join: no input focused, name node replaced, value kept',st['replaced'] and st['active'] not in ('INPUT','TEXTAREA') and st['myName']=='QA Undo '+n,st)
    und=pg.evaluate("()=>{const i=document.getElementById('startName');const v=i.value;i.focus();document.execCommand('undo');const r=i.value;i.blur();return [v,r]}")
    ok(f'{n} undo after join has nothing to undo (control canUndo={canUndo})',und[0]==und[1],und)
    pv=pg.evaluate("()=>{const e=new InputEvent('beforeinput',{inputType:'historyUndo',cancelable:true,bubbles:true});document.getElementById('msgText').dispatchEvent(e);return e.defaultPrevented}")
    ok(f'{n} beforeinput historyUndo prevented',pv)
    pg.evaluate("()=>{const m=document.getElementById('msgText');m.style.display='';m.focus()}")
    pg.mouse.click(200,450); pg.wait_for_timeout(300)
    ok(f'{n} map tap blurs input',pg.evaluate("()=>document.activeElement.id")!='msgText')
    pg.evaluate("()=>{openStylePanel();document.getElementById('msgText').focus();closeStylePanel()}")
    ok(f'{n} closing 🎨 panel blurs input',pg.evaluate("()=>document.activeElement.id")!='msgText')
    pg.evaluate("()=>{const m=document.getElementById('msgText');m.value='hi';document.getElementById('riderList').value='';sendMessage()}"); pg.wait_for_timeout(300)
    ok(f'{n} after send: msg box cleared, blurred, replaced',pg.evaluate("()=>{const m=document.getElementById('msgText');return m.value===''&&document.activeElement!==m}"))
    pg.evaluate("()=>{try{ws.send(JSON.stringify({type:'leave'}))}catch(e){}}")
    ok(f'{n} no page errors',not E,E); b.close()
print('ALL PASS' if all(R) else 'SOME FAIL')
