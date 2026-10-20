from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
import json, time, uuid, secrets, pathlib, asyncio

app = FastAPI()

groups = {}

INDEX_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover">
<title>Water Tracker</title>
<link rel="manifest" href="/manifest.json">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Tracker">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  html,body{margin:0;height:100%;font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#0b1d33;color:#e8eef7;overflow:hidden}
  #map{
    position:absolute;
    top:160px;
    left:0;right:0;bottom:0;
    display:none;
  }
  #bar{
    position:absolute;
    top:0;left:0;right:0;
    z-index:1000;
    display:none;
    flex-direction:column;
    gap:6px;
    padding: calc(env(safe-area-inset-top, 20px) + 12px) 8px 10px 8px;
    background:rgba(11,29,51,.95);
    box-sizing:border-box;
  }
  .row{display:flex;gap:6px;align-items:center}
  #bar input, #bar select{
    flex:1;min-width:0;padding:8px 10px;border-radius:8px;
    border:1px solid #2a4a6f;background:#132a45;color:#e8eef7;font-size:15px;
  }
  #bar button{
    padding:8px 12px;border-radius:8px;border:0;
    background:#2f9e6b;color:#fff;font-weight:600;font-size:14px;
    white-space:nowrap;
  }
  #bar button.center{background:#3b82f6}
  #bar button.find{background:#f59e0b}
  #bar button.msg{background:#8b5cf6}
  #bar button.broadcast{background:#ec4899}
  #status{
    position:absolute;bottom:8px;left:8px;right:8px;z-index:1000;
    padding:6px 10px;border-radius:8px;background:rgba(11,29,51,.9);
    font-size:12px;color:#9fb3c8;text-align:center;display:none;
  }
  #banner{
    position:absolute;top:170px;left:8px;right:8px;z-index:1001;
    padding:10px 12px;border-radius:8px;background:#8b5cf6;color:#fff;
    font-size:14px;display:none;text-align:center;
  }
  #banner button{margin-top:6px;padding:6px 12px;border-radius:6px;border:0;background:#fff;color:#8b5cf6;font-weight:600}
  .leaflet-container{background:#0b1d33}
  #msgBox{display:none}
  #nameScreen{
    position:absolute;inset:0;z-index:2000;background:#0b1d33;
    display:flex;flex-direction:column;align-items:center;justify-content:center;
    gap:16px;padding:20px;
  }
  #nameScreen h1{margin:0;font-size:26px}
  #nameScreen input{
    padding:14px;border-radius:12px;border:1px solid #2a4a6f;
    background:#132a45;color:#e8eef7;font-size:18px;width:100%;max-width:260px;text-align:center;
  }
  #nameScreen button{
    padding:14px 32px;border-radius:12px;border:0;background:#2f9e6b;
    color:#fff;font-weight:600;font-size:18px;
  }
</style>
</head>
<body>
<div id="nameScreen">
  <h1>Water Tracker</h1>
  <input id="startName" placeholder="Enter your name" autocomplete="off" autocorrect="off">
  <button onclick="startApp()">Start</button>
</div>
<div id="banner"></div>
<div id="bar">
  <div class="row">
    <button class="center" onclick="centerOnMe()">Center</button>
    <select id="riderList" onchange="onRiderSelect()">
      <option value="">-- Riders --</option>
    </select>
    <button id="findBtn" class="find" onclick="toggleFind()" style="display:none">Find</button>
  </div>
  <div class="row" id="msgBox">
    <input id="msgText" placeholder="Message...">
    <button class="msg" onclick="sendMessage()">Send</button>
    <button class="broadcast" onclick="broadcastMessage()">All</button>
  </div>
</div>
<div id="map"></div>
<div id="status"></div>
<script>
const map = L.map('map', {zoomControl:false}).setView([35.5,-77.0], 12);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
  attribution: '&copy; OpenStreetMap'
}).addTo(map);
L.control.zoom({position:'bottomright'}).addTo(map);

const riders = {};
const lastSeen = {};
const positions = {};
let me = localStorage.getItem('trackerId') || null;
if (!me) {
  me = Math.random().toString(36).slice(2, 10);
  localStorage.setItem('trackerId', me);
}
let myName = '';
let myLatLng = null;
let watchId = null;
let ws = null;
let sharing = false;
let pingTimer = null;
let lastListKey = '';
let findTarget = null;
let findLine = null;

function status(t){ 
  const el = document.getElementById('status');
  if (el.textContent !== t) el.textContent = t;
}

function showBanner(text, fromId){
  const b = document.getElementById('banner');
  b.innerHTML = text + (fromId ? '<br><button onclick="replyToLast(\'' + fromId + '\')">Reply</button>' : '');
  b.style.display = 'block';
  setTimeout(() => { b.style.display = 'none'; }, 12000);
}

function replyToLast(fromId){
  const sel = document.getElementById('riderList');
  if (positions[fromId]){
    sel.value = fromId;
    document.getElementById('msgBox').style.display = 'flex';
    document.getElementById('msgText').focus();
    onRiderSelect();
  }
  document.getElementById('banner').style.display = 'none';
}

function clearFindLine(){
  if (findLine){
    map.removeLayer(findLine);
    findLine = null;
  }
  findTarget = null;
  document.getElementById('findBtn').textContent = 'Find';
}

function centerOnMe(){
  if (myLatLng){
    map.panTo(myLatLng);
    map.setZoom(16);
  }
}

function onRiderSelect(){
  const sel = document.getElementById('riderList');
  const id = sel.value;
  document.getElementById('msgBox').style.display = id ? 'flex' : 'none';
  document.getElementById('findBtn').style.display = id ? 'inline-block' : 'none';
  if (id && positions[id]){
    map.panTo([positions[id].lat, positions[id].lon]);
  }
  if (findTarget && findTarget !== id) clearFindLine();
}

function toggleFind(){
  const sel = document.getElementById('riderList');
  const id = sel.value;
  if (!id || !myLatLng || !positions[id]) return;
  if (findTarget === id){
    clearFindLine();
    return;
  }
  findTarget = id;
  document.getElementById('findBtn').textContent = 'Stop';
  updateFindLine();
}

function updateFindLine(){
  if (!findTarget || !myLatLng || !positions[findTarget]) {
    clearFindLine();
    return;
  }
  const target = [positions[findTarget].lat, positions[findTarget].lon];
  if (findLine){
    findLine.setLatLngs([myLatLng, target]);
  } else {
    findLine = L.polyline([myLatLng, target], {color:'#f59e0b', weight:4, opacity:0.85}).addTo(map);
  }
}

function sendMessage(){
  const sel = document.getElementById('riderList');
  const to = sel.value;
  const text = document.getElementById('msgText').value.trim();
  if (!to || !text) return;
  if (ws && ws.readyState === 1){
    ws.send(JSON.stringify({type:'msg', to:to, text:text}));
    document.getElementById('msgText').value = '';
    status('Message sent');
  }
}

function broadcastMessage(){
  const text = document.getElementById('msgText').value.trim();
  if (!text) return;
  if (ws && ws.readyState === 1){
    ws.send(JSON.stringify({type:'broadcast', text:text}));
    document.getElementById('msgText').value = '';
    status('Broadcast sent');
  }
}

function haversine(lat1, lon1, lat2, lon2){
  const R = 6371000;
  const toRad = d => d * Math.PI / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a = Math.sin(dLat/2)**2 + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon/2)**2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
}

function updateRiderList(){
  const sel = document.getElementById('riderList');
  if (!myLatLng) return;
  const others = [];
  for (const id in positions){
    if (id === me) continue;
    const p = positions[id];
    const dist = haversine(myLatLng[0], myLatLng[1], p.lat, p.lon);
    others.push({id, name: p.name, dist});
  }
  others.sort((a,b) => a.dist - b.dist);
  const key = others.map(o => o.id + ':' + Math.round(o.dist)).join('|');
  if (key === lastListKey) return;
  lastListKey = key;

  const current = sel.value;
  sel.innerHTML = '<option value="">-- Riders --</option>';
  others.forEach(o => {
    const opt = document.createElement('option');
    opt.value = o.id;
    const miles = (o.dist / 1609.34).toFixed(2);
    opt.textContent = `${o.name} (${miles} mi)`;
    sel.appendChild(opt);
  });
  if (current && positions[current]) sel.value = current;
  document.getElementById('msgBox').style.display = others.length ? 'flex' : 'none';
  document.getElementById('findBtn').style.display = (sel.value && others.length) ? 'inline-block' : 'none';
}

function updateMyMarker(lat, lon){
  myLatLng = [lat, lon];
  lastSeen[me] = Date.now();
  positions[me] = {lat, lon, name: myName};
  if (riders[me]){
    riders[me].setLatLng(myLatLng);
  } else {
    const icon = L.divIcon({
      className: '',
      html: `<div style="
        width:0;height:0;
        border-left:18px solid transparent;
        border-right:18px solid transparent;
        border-bottom:40px solid #22c55e;
        filter:drop-shadow(0 0 6px #fff) drop-shadow(0 0 10px #22c55e);
        position:relative;
      ">
        <div style="
          position:absolute;
          top:8px;left:-20px;
          width:40px;text-align:center;
          color:#fff;font-weight:900;font-size:11px;
          text-shadow:0 0 4px #000, 0 0 6px #000;
        ">YOU</div>
      </div>`,
      iconSize:[36,40],
      iconAnchor:[18,40]
    });
    riders[me] = L.marker(myLatLng,{icon, zIndexOffset:2000}).addTo(map).bindPopup(myName + ' (you)');
  }
  map.panTo(myLatLng);
  updateFindLine();
  updateRiderList();
}

function connect(){
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(proto + '://' + location.host + '/ws');
  ws.onopen = () => {
    status('Connected');
    ws.send(JSON.stringify({
      type: 'join',
      id: me,
      name: myName,
      code: 'ENCSR'
    }));
    if (pingTimer) clearInterval(pingTimer);
    pingTimer = setInterval(() => {
      if (ws && ws.readyState === 1) ws.send(JSON.stringify({type:'ping'}));
    }, 15000);
  };
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.type === 'joined'){
      status('Sharing — ENCSR');
      if (myLatLng) updateMyMarker(myLatLng[0], myLatLng[1]);
    }
    else if (m.type === 'error'){ status(m.msg); }
    else if (m.type === 'riders'){
      m.riders.forEach(r => upsert(r));
      updateRiderList();
    }
    else if (m.type === 'pos') {
      upsert(m);
      updateRiderList();
    }
    else if (m.type === 'leave') remove(m.id);
    else if (m.type === 'msg'){
      const txt = (m.from || 'Someone') + ': ' + m.text;
      showBanner(txt, m.fromId);
    }
  };
  ws.onclose = () => {
    if (pingTimer) clearInterval(pingTimer);
    if (sharing) {
      status('Reconnecting...');
      setTimeout(connect, 3000);
    }
  };
}

function upsert(r){
  if (r.lat == null && r.lon == null) return;
  const name = r.name || 'Rider';
  lastSeen[r.id] = Date.now();
  positions[r.id] = {lat: r.lat, lon: r.lon, name};
  if (r.id === me){
    updateMyMarker(r.lat, r.lon);
    return;
  }
  if (riders[r.id]){
    riders[r.id].setLatLng([r.lat, r.lon]);
    riders[r.id].setPopupContent(name);
  } else {
    const icon = L.divIcon({
      className: '',
      html: `<div style="
        width:16px;height:16px;border-radius:50%;
        background:#4aa3ff;
        border:2px solid #fff;
        box-shadow:0 0 4px rgba(0,0,0,.5);
      "></div>`,
      iconSize:[16,16],
      iconAnchor:[8,8]
    });
    riders[r.id] = L.marker([r.lat, r.lon],{icon}).addTo(map).bindPopup(name);
  }
  if (findTarget === r.id) updateFindLine();
}

function remove(id){
  if (id === me) return;
  if (riders[id]){
    map.removeLayer(riders[id]);
    delete riders[id];
    delete lastSeen[id];
    delete positions[id];
  }
  if (findTarget === id) clearFindLine();
  lastListKey = '';
  updateRiderList();
}

setInterval(() => {
  const now = Date.now();
  for (const id in lastSeen){
    if (id === me) continue;
    if (now - lastSeen[id] > 120000) remove(id);
  }
}, 10000);

document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible' && sharing && (!ws || ws.readyState !== 1)) {
    setTimeout(connect, 500);
  }
});

function startApp(){
  const name = document.getElementById('startName').value.trim();
  if (!name){
    document.getElementById('startName').focus();
    return;
  }
  myName = name;
  document.getElementById('nameScreen').style.display = 'none';
  document.getElementById('map').style.display = 'block';
  document.getElementById('bar').style.display = 'flex';
  document.getElementById('status').style.display = 'block';
  setTimeout(() => {
    map.invalidateSize();
  }, 300);
  sharing = true;
  connect();
  watchId = navigator.geolocation.watchPosition(p => {
    const lat = p.coords.latitude;
    const lon = p.coords.longitude;
    updateMyMarker(lat, lon);
    if (ws && ws.readyState === 1){
      ws.send(JSON.stringify({type:'pos', lat:lat, lon:lon}));
    }
  }, e => {
    status('Location error: ' + e.message);
  }, {enableHighAccuracy:true, maximumAge:3000, timeout:15000});
}

if ('wakeLock' in navigator){ navigator.wakeLock.request('screen').catch(()=>{}); }
</script>
</body>
</html>"""

@app.get("/")
async def index():
    return HTMLResponse(INDEX_HTML)

@app.get("/manifest.json")
async def manifest():
    return FileResponse(pathlib.Path(__file__).parent / "manifest.json")

@app.on_event("startup")
async def startup():
    asyncio.create_task(periodic_broadcast())

async def periodic_broadcast():
    while True:
        await asyncio.sleep(6)
        for code in list(groups.keys()):
            if groups.get(code):
                await broadcast(code, {"type": "riders", "riders": public_list(code)})

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    rider_id = None
    code = None
    try:
        raw = await ws.receive_text()
        msg = json.loads(raw)
        if msg.get("type") != "join":
            await ws.close()
            return
        rider_id = msg.get("id") or str(uuid.uuid4())[:8]
        name = (msg.get("name") or "Rider").strip()[:20] or "Rider"
        code = (msg.get("code") or "ENCSR").strip().upper()
        if code not in groups:
            groups[code] = {}
        groups[code][rider_id] = {"name": name, "lat": None, "lon": None,
                                  "updated": time.time(), "ws": ws}
        await ws.send_text(json.dumps({"type": "joined", "id": rider_id, "code": code}))
        await broadcast(code, {"type": "riders", "riders": public_list(code)})

        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            t = msg.get("type")
            if t == "pos":
                g = groups.get(code, {})
                if rider_id in g:
                    g[rider_id]["lat"] = float(msg["lat"])
                    g[rider_id]["lon"] = float(msg["lon"])
                    g[rider_id]["updated"] = time.time()
                    await broadcast(code, {"type": "pos", "id": rider_id,
                                    "name": g[rider_id]["name"],
                                    "lat": g[rider_id]["lat"],
                                    "lon": g[rider_id]["lon"]})
            elif t == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))
            elif t == "msg":
                to_id = msg.get("to")
                text = (msg.get("text") or "").strip()[:200]
                if to_id and text and code in groups and to_id in groups[code]:
                    target = groups[code][to_id]
                    try:
                        await target["ws"].send_text(json.dumps({
                            "type": "msg",
                            "from": groups[code][rider_id]["name"],
                            "fromId": rider_id,
                            "text": text
                        }))
                    except Exception:
                        pass
            elif t == "broadcast":
                text = (msg.get("text") or "").strip()[:200]
                if text and code in groups:
                    payload = json.dumps({
                        "type": "msg",
                        "from": groups[code][rider_id]["name"] + " (all)",
                        "fromId": None,
                        "text": text
                    })
                    for rid, r in list(groups[code].items()):
                        if rid == rider_id:
                            continue
                        try:
                            await r["ws"].send_text(payload)
                        except Exception:
                            pass
    except WebSocketDisconnect:
        pass
    finally:
        if rider_id and code:
            g = groups.get(code, {})
            if rider_id in g:
                g.pop(rider_id, None)
                await broadcast(code, {"type": "leave", "id": rider_id})
                if not g:
                    groups.pop(code, None)

def public_list(code):
    now = time.time()
    out = []
    for rid, r in groups.get(code, {}).items():
        if r["lat"] is None:
            continue
        if now - r["updated"] > 180:
            continue
        out.append({"id": rid, "name": r["name"], "lat": r["lat"],
                    "lon": r["lon"], "age": round(now - r["updated"], 1)})
    return out

async def broadcast(code, msg):
    payload = json.dumps(msg)
    dead = []
    for rid, r in list(groups.get(code, {}).items()):
        try:
            await r["ws"].send_text(payload)
        except Exception:
            dead.append(rid)
    for rid in dead:
        groups.get(code, {}).pop(rid, None)