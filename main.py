from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
import json, time, uuid, secrets, pathlib, asyncio

app = FastAPI()

# group_code -> { rider_id -> {name, lat, lon, updated, ws} }
groups = {}

INDEX_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<title>Water Tracker</title>
<link rel="manifest" href="/manifest.json">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Tracker">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  html,body{margin:0;height:100%;font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#0b1d33;color:#e8eef7;overflow:hidden}
  #map{height:100%}
  #bar{position:absolute;top:0;left:0;right:0;z-index:1000;display:flex;gap:8px;align-items:center;padding:10px 12px;background:rgba(11,29,51,.88);backdrop-filter:blur(6px)}
  #bar input{flex:1;min-width:0;padding:10px 12px;border-radius:10px;border:1px solid #2a4a6f;background:#132a45;color:#e8eef7;font-size:16px}
  #bar button{padding:10px 14px;border-radius:10px;border:0;background:#2f9e6b;color:#fff;font-weight:600;font-size:15px;white-space:nowrap}
  #bar button.stop{background:#c0392b}
  #bar button.center{background:#3b82f6}
  #bar button:disabled{opacity:.45}
  #status{position:absolute;bottom:12px;left:12px;right:12px;z-index:1000;padding:8px 12px;border-radius:10px;background:rgba(11,29,51,.85);font-size:13px;color:#9fb3c8;text-align:center}
  .leaflet-container{background:#0b1d33}
</style>
</head>
<body>
<div id="bar">
  <input id="name" placeholder="Your name" autocomplete="off" autocorrect="off">
  <input id="code" placeholder="Group code" autocomplete="off" autocorrect="off" style="max-width:110px">
  <button id="go" onclick="toggle()">Start Sharing</button>
  <button id="center" class="center" onclick="centerOnMe()" style="display:none">Center on Me</button>
</div>
<div id="map"></div>
<div id="status">Create or enter a group code. Allow location when prompted.</div>
<script>
const map = L.map('map', {zoomControl:false}).setView([35.5,-77.0], 12);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
  attribution: '&copy; OpenStreetMap'
}).addTo(map);
L.control.zoom({position:'bottomright'}).addTo(map);

const riders = {};
let me = null;
let myLatLng = null;
let watchId = null;
let ws = null;
let sharing = false;
let pingTimer = null;

function status(t){ document.getElementById('status').textContent = t; }

function clearAllMarkers(){
  for (const id in riders) map.removeLayer(riders[id]);
  for (const id in riders) delete riders[id];
}

function centerOnMe(){
  if (myLatLng){
    map.panTo(myLatLng);
    map.setZoom(15);
  } else if (me && riders[me]){
    map.panTo(riders[me].getLatLng());
    map.setZoom(15);
  } else {
    status('Waiting for your location...');
  }
}

function updateMyMarker(lat, lon){
  myLatLng = [lat, lon];
  if (!me) return;
  if (riders[me]){
    riders[me].setLatLng(myLatLng);
  } else {
    const icon = L.divIcon({className:'', html:`<div style="width:16px;height:16px;border-radius:50%;background:#2f9e6b;border:2px solid #fff;box-shadow:0 0 6px rgba(0,0,0,.6)"></div>`, iconSize:[16,16], iconAnchor:[8,8]});
    riders[me] = L.marker(myLatLng,{icon}).addTo(map).bindPopup((document.getElementById('name').value || 'You') + ' (you)');
  }
}

function connect(){
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(proto + '://' + location.host + '/ws');
  ws.onopen = () => {
    ws.send(JSON.stringify({type:'join', name: document.getElementById('name').value || 'Rider',
                           code: document.getElementById('code').value.trim()}));
    pingTimer = setInterval(() => {
      if (ws && ws.readyState === 1) ws.send(JSON.stringify({type:'ping'}));
    }, 10000);
  };
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.type === 'joined'){
      me = m.id;
      status('Sharing in group ' + m.code + '. Your dot is green.');
      document.getElementById('center').style.display = 'inline-block';
      if (myLatLng) updateMyMarker(myLatLng[0], myLatLng[1]);
    }
    else if (m.type === 'error'){ status(m.msg); toggle(); }
    else if (m.type === 'riders'){
      const seen = new Set();
      m.riders.forEach(r => { upsert(r); seen.add(r.id); });
      for (const id in riders){
        if (id !== me && !seen.has(id)) remove(id);
      }
    }
    else if (m.type === 'pos') upsert(m);
    else if (m.type === 'leave') remove(m.id);
  };
  ws.onclose = () => {
    if (pingTimer) clearInterval(pingTimer);
    if (sharing) setTimeout(connect, 1500);
  };
}

function upsert(r){
  if (!r.lat && r.lat !== 0) return;
  const name = r.name || 'Rider';
  if (r.id === me){
    updateMyMarker(r.lat, r.lon);
    return;
  }
  if (riders[r.id]){
    riders[r.id].setLatLng([r.lat, r.lon]);
    riders[r.id].setPopupContent(name);
  } else {
    const icon = L.divIcon({className:'', html:`<div style="width:16px;height:16px;border-radius:50%;background:#4aa3ff;border:2px solid #fff;box-shadow:0 0 6px rgba(0,0,0,.6)"></div>`, iconSize:[16,16], iconAnchor:[8,8]});
    riders[r.id] = L.marker([r.lat,r.lon],{icon}).addTo(map).bindPopup(name);
  }
}

function remove(id){
  if (riders[id]){
    map.removeLayer(riders[id]);
    delete riders[id];
  }
}

function toggle(){
  if (!sharing){
    const name = document.getElementById('name').value.trim();
    if (!name){ document.getElementById('name').focus(); status('Enter your name first.'); return; }
    if (!navigator.geolocation){ status('Geolocation not supported.'); return; }
    clearAllMarkers();
    me = null;
    myLatLng = null;
    sharing = true;
    document.getElementById('go').textContent = 'Stop';
    document.getElementById('go').classList.add('stop');
    document.getElementById('name').disabled = true;
    document.getElementById('code').disabled = true;
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
  } else {
    sharing = false;
    document.getElementById('go').textContent = 'Start Sharing';
    document.getElementById('go').classList.remove('stop');
    document.getElementById('name').disabled = false;
    document.getElementById('code').disabled = false;
    document.getElementById('center').style.display = 'none';
    if (watchId !== null) navigator.geolocation.clearWatch(watchId);
    watchId = null;
    if (pingTimer) clearInterval(pingTimer);
    if (ws) ws.close();
    status('Stopped.');
  }
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
        await asyncio.sleep(8)
        for code in list(groups.keys()):
            if groups.get(code):
                await broadcast(code, {"type": "riders", "riders": public_list(code)})

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    rider_id = str(uuid.uuid4())[:8]
    try:
        raw = await ws.receive_text()
        msg = json.loads(raw)
        if msg.get("type") != "join":
            await ws.close()
            return
        name = (msg.get("name") or "Rider").strip()[:20] or "Rider"
        code = (msg.get("code") or "").strip().upper()
        if not code:
            code = secrets.token_hex(3).upper()
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
    except WebSocketDisconnect:
        pass
    finally:
        for code, g in list(groups.items()):
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
        # drop riders with no update in 60s
        if now - r["updated"] > 60:
            continue
        out.append({"id": rid, "name": r["name"], "lat": r["lat"],
                    "lon": r["lon"], "age": round(now - r["updated"], 1)})
    return out

async def broadcast(code, msg):
    payload = json.dumps(msg)
    dead = []
    for rid, r in groups.get(code, {}).items():
        try:
            await r["ws"].send_text(payload)
        except Exception:
            dead.append(rid)
    for rid in dead:
        groups.get(code, {}).pop(rid, None)