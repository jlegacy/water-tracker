from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
import json, time, uuid, secrets, pathlib, asyncio, os

# Safety / stale-rider settings (override with env vars for testing)
STALE_SECS = float(os.environ.get("STALE_SECS", "90"))          # no update for this long -> stale alert
STALE_CHECK_SECS = float(os.environ.get("STALE_CHECK_SECS", "15"))  # how often the server checks
PURGE_SECS = float(os.environ.get("PURGE_SECS", "1800"))        # forget a silent rider after 30 min
# TODO(push): stale/missing-rider alerts are currently delivered over the WebSocket only, so a
# phone whose app is fully suspended will not get them until it reopens. Wire real push here
# (APNs for iOS, FCM for Android) once credentials exist: register device tokens on 'join',
# then send a push from stale_monitor() alongside the WebSocket 'alert'. See README-push.md.

app = FastAPI()

groups = {}

# Allowed group names. Each is its own isolated group; matching is case-insensitive.
GROUP_CODES = ["Wake Me Up", "Spray & Pray", "Throttle Bottoms", "Salty Seadogs", "Wet Willies", "Full Send Fleet", "Buoy Band", "Rooster Tail Rebels"]
GROUP_BY_UPPER = {c.upper(): c for c in GROUP_CODES}

INDEX_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover">
<title>Water Tracker</title>
<link rel="manifest" href="/manifest.json">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="icon" type="image/png" href="/icon-192.png">
<meta name="theme-color" content="#0b1d51">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Tracker">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/leaflet-rotate@0.2.8/dist/leaflet-rotate.js"></script>
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
  #bar input[readonly]{background:#0f2038;color:#9fb3c8;cursor:default}
  #bar button{
    padding:8px 12px;border-radius:8px;border:0;
    background:#2f9e6b;color:#fff;font-weight:600;font-size:14px;
    white-space:nowrap;
  }
  #bar button.center{background:#3b82f6}
  #bar button.find{background:#f59e0b}
  #bar button.msg{background:#8b5cf6}
  #bar button.broadcast{background:#ec4899}
  #bar button.ramps{background:#0891b2}
  #bar button.ramps.on{background:#0e7490;box-shadow:inset 0 0 0 2px #67e8f9}
  .rampIcon{display:flex;align-items:center;justify-content:center;width:26px;height:26px;border-radius:6px;background:#fff;border:2px solid #0891b2;font-size:15px;box-shadow:0 1px 3px rgba(0,0,0,.4)}
  .rampIcon.marina{border-color:#1e3a8a;border-radius:50%}
  #rampToast{position:fixed;left:50%;bottom:90px;transform:translateX(-50%);background:rgba(15,32,56,.95);color:#fff;padding:8px 14px;border-radius:8px;font-size:14px;z-index:2000;display:none;max-width:85%;text-align:center}
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
  #banner .drain{height:4px;background:rgba(255,255,255,.25);border-radius:2px;margin-top:8px;overflow:hidden}
  #banner .drainFill{height:100%;width:100%;background:#fff}
  #banner button{margin-top:6px;padding:6px 12px;border-radius:6px;border:0;background:#fff;color:#8b5cf6;font-weight:600}
  .leaflet-container{background:#0b1d33}
  #msgBox{display:none}
  #nameScreen{
    position:absolute;inset:0;z-index:2000;background:#0b1d33;
    display:flex;flex-direction:column;align-items:center;justify-content:center;
    gap:14px;padding:20px;
  }
  #nameScreen h1{margin:0;font-size:26px}
  #nameScreen input{
    padding:14px;border-radius:12px;border:1px solid #2a4a6f;
    background:#132a45;color:#e8eef7;font-size:18px;width:100%;max-width:260px;text-align:center;
  }
  #nameScreen select{font-size:18px;padding:12px;border-radius:10px;width:100%;max-width:320px}
  #nameScreen input[readonly]{background:#0f2038;color:#9fb3c8}
  #nameScreen button{
    padding:14px 32px;border-radius:12px;border:0;background:#2f9e6b;
    color:#fff;font-weight:600;font-size:18px;
  }
  .mapBtn{
    position:absolute;right:10px;z-index:1000;
    min-width:96px;min-height:48px;padding:10px 14px;border-radius:12px;border:2px solid #fff;
    color:#fff;font-weight:700;font-size:16px;box-shadow:0 2px 6px rgba(0,0,0,.5);display:none;
  }
  #headingBtn{top:172px;background:#0f766e}
  #recenterBtn{top:230px;background:#3b82f6}
  .groupLabel{font-size:13px;color:#9fb3c8;margin-bottom:-6px}
  #bar button.leader{background:#475569}
  #bar button.leader.on{background:#dc2626}
  #banner.alert{background:#dc2626}
</style>
</head>
<body>
<div id="nameScreen">
  <h1>Water Tracker</h1>
  <div class="groupLabel">Group</div>
  <select id="startGroup" required>
    <option value="" disabled selected>-- Select your group --</option>
    <option value="Buoy Band">Buoy Band</option>
    <option value="Full Send Fleet">Full Send Fleet</option>
    <option value="Rooster Tail Rebels">Rooster Tail Rebels</option>
    <option value="Salty Seadogs">Salty Seadogs</option>
    <option value="Spray &amp; Pray">Spray &amp; Pray</option>
    <option value="Throttle Bottoms">Throttle Bottoms</option>
    <option value="Wake Me Up">Wake Me Up</option>
    <option value="Wet Willies">Wet Willies</option>
  </select>
  <div class="groupLabel">Your Name</div>
  <input id="startName" placeholder="Enter your name" autocomplete="off" autocorrect="off">
  <button onclick="startApp()">Start</button>
</div>
<div id="banner"></div>
<div id="bar">
  <div class="row">
    <input id="groupDisplay" value="" readonly style="max-width:140px;text-align:center;font-weight:600">
    <button class="center" onclick="centerOnMe()">Center</button>
    <select id="riderList" onchange="onRiderSelect()">
      <option value="">-- Riders --</option>
    </select>
    <button id="findBtn" class="find" onclick="toggleFind()" style="display:none">Find</button>
    <button id="leaderBtn" class="leader" onclick="toggleLeader()">Leader</button>
  </div>
  <div class="row" id="msgBox">
    <input id="msgText" placeholder="Message...">
    <button class="msg" onclick="sendMessage()">Send</button>
    <button class="broadcast" onclick="broadcastMessage()">All</button>
    <button id="rampsBtn" class="ramps" onclick="toggleRamps()">Ramps</button>
  </div>
</div>
<div id="map"></div>
<div id="status"></div>
<div id="rampToast"></div>
<button id="headingBtn" class="mapBtn" onclick="toggleHeadingMode()">North Up</button>
<button id="recenterBtn" class="mapBtn" onclick="recenter()">Re-center</button>
<script>
const map = L.map('map', {
  zoomControl: false,
  rotate: true,
  bearing: 0,
  zoomSnap: 0.5,
  zoomDelta: 0.5,
  touchZoom: true,
  bounceAtZoomLimits: false
}).setView([35.5,-77.0], 12);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
  attribution: '&copy; OpenStreetMap contributors'
}).addTo(map);
const zoomCtl = L.control.zoom({position:'bottomright'}).addTo(map);
zoomCtl.getContainer().addEventListener('click', () => setFollow(false));

// Enable two-finger spin
if (map.touchRotate) map.touchRotate.enable();

// Any user pan/zoom turns off follow-me (programmatic moves don't fire these)
map.on('dragstart', () => setFollow(false));
const mapEl = document.getElementById('map');
mapEl.addEventListener('wheel', () => setFollow(false), {passive:true});
mapEl.addEventListener('touchstart', e => { if (e.touches.length > 1) setFollow(false); }, {passive:true});
mapEl.addEventListener('dblclick', () => setFollow(false));

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
// --- Power saving: outbound throttle, reconnect backoff, offline queue ---
const SEND_INTERVAL_MS = 7000;   // send at most every 7 s...
const SEND_DISTANCE_M = 15;      // ...unless we've moved 15 m since the last send
const KEEPALIVE_MS = 25000;      // only ping if nothing was sent for 25 s
const MAX_QUEUE = 10;            // positions kept while disconnected
let lastSent = null;             // {lat, lon, t}
let lastSendAt = 0;              // any message sent (keep-alive tracking)
let pendingFix = null;           // latest fix not yet sent
let sendTimer = null;
let posQueue = [];               // unsent positions while offline
let reconnectDelay = 1000;
let reconnectTimer = null;
// --- Incoming batching / background pause ---
const pendingRiders = {};        // id -> latest update, flushed at most once a second
let renderDirty = false;
const STALE_MS = 90000;          // grey out riders silent this long
const REMOVE_MS = 30 * 60000;    // forget riders silent for 30 min
function isHidden(){ return document.visibilityState === 'hidden'; }
let lastListKey = '';
let findTarget = null;
let findLine = null;

// Map orientation: 'north' (default) or 'heading'
let headingMode = 'north'; // always start north-up on load
let lastHeading = null;   // last good course in degrees (0 = north)
let lastFix = null;       // previous fix, used to compute course when GPS gives none
const MIN_SPEED = 1;      // m/s; below this, hold the last heading

// Follow-me: map tracks my position until the user drags/zooms
let followMe = true;

// Breadcrumb trail
let breadcrumb = [];
let breadcrumbLine = null;
const MAX_BREADCRUMB = 500;

function status(t){ 
  const el = document.getElementById('status');
  if (el.textContent !== t) el.textContent = t;
}

let bannerTimer = null;
const BANNER_MS = 12000;
function showBanner(text, fromId){
  const b = document.getElementById('banner');
  b.innerHTML = text + (fromId ? '<br><button onclick="replyToLast(\'' + fromId + '\')">Reply</button>' : '')
    + '<div class="drain"><div class="drainFill"></div></div>';
  b.style.display = 'block';
  const fill = b.querySelector('.drainFill');
  fill.style.transition = 'none';
  fill.style.width = '100%';
  void fill.offsetWidth; // restart animation
  fill.style.transition = 'width ' + BANNER_MS + 'ms linear';
  fill.style.width = '0%';
  if (bannerTimer) clearTimeout(bannerTimer);
  bannerTimer = setTimeout(() => { b.style.display = 'none'; bannerTimer = null; }, BANNER_MS);
}

function selectRiderFromMap(id){
  const sel = document.getElementById('riderList');
  if (!sel || !positions[id]) return;
  if (![...sel.options].some(o => o.value === id)){ lastListKey = null; updateRiderList(); }
  if (![...sel.options].some(o => o.value === id)) return;
  sel.value = id;
  onRiderSelect();
  try { document.getElementById('msgText').focus({preventScroll:true}); } catch(e){}
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

// Route line to a ramp/marina (same style/behavior as the rider Find line)
let rampRoute = null, rampRouteLine = null, rampItems = [];
function clearRampRoute(){
  if (rampRouteLine){ map.removeLayer(rampRouteLine); rampRouteLine = null; }
  rampRoute = null;
}
function updateRampRoute(){
  if (!rampRoute) return;
  if (!myLatLng){ clearRampRoute(); return; }
  const t = [rampRoute.lat, rampRoute.lon];
  if (rampRouteLine) rampRouteLine.setLatLngs([myLatLng, t]);
  else rampRouteLine = L.polyline([myLatLng, t], {color:'#f59e0b', weight:4, opacity:0.85}).addTo(map);
}
function toggleRampRoute(i){
  const it = rampItems[i];
  if (!it) return;
  if (rampRoute === it){ clearRampRoute(); map.closePopup(); return; }
  if (!myLatLng){ rampToast('Waiting for your location'); return; }
  if (findTarget) clearFindLine();
  clearRampRoute();
  rampRoute = it;
  updateRampRoute();
  map.closePopup();
}

function centerOnMe(){
  recenter();
}

function setFollow(on){
  followMe = on;
  document.getElementById('recenterBtn').style.display = on ? 'none' : 'block';
}

function recenter(){
  setFollow(true);
  if (myLatLng) map.setView(myLatLng, Math.max(map.getZoom(), 16));
  applyBearing();
}

function updateHeadingBtn(){
  document.getElementById('headingBtn').textContent = headingMode === 'heading' ? 'Heading Up' : 'North Up';
}

function toggleHeadingMode(){
  headingMode = headingMode === 'heading' ? 'north' : 'heading';
  updateHeadingBtn();
  applyBearing();
}

// Point the YOU triangle in the real direction of travel on screen
function rotateMe(){
  const el = document.querySelector('.me-arrow');
  if (!el || lastHeading == null) return;
  const b = map.getBearing ? map.getBearing() : 0;
  el.style.transform = 'rotate(' + (lastHeading + b) + 'deg)';
}
function applyBearing(){
  if (!map.setBearing) return;
  if (headingMode === 'heading' && lastHeading != null){
    // Rotate map so direction of travel points up
    map.setBearing(-lastHeading);
  } else {
    map.setBearing(0);
  }
  rotateMe();
}

// Update lastHeading from a fix. heading in degrees (may be null/NaN), speed in m/s (may be null)
function updateHeading(lat, lon, heading, speed){
  let course = null;
  let spd = speed;
  if (lastFix){
    const d = haversine(lastFix.lat, lastFix.lon, lat, lon);
    const dt = (Date.now() - lastFix.t) / 1000;
    if (spd == null && dt > 0) spd = d / dt;
    if ((heading == null || isNaN(heading)) && d > 5){
      const toRad = x => x * Math.PI / 180;
      const y = Math.sin(toRad(lon - lastFix.lon)) * Math.cos(toRad(lat));
      const x = Math.cos(toRad(lastFix.lat)) * Math.sin(toRad(lat)) -
                Math.sin(toRad(lastFix.lat)) * Math.cos(toRad(lat)) * Math.cos(toRad(lon - lastFix.lon));
      heading = (Math.atan2(y, x) * 180 / Math.PI + 360) % 360;
    }
  }
  if (!lastFix || haversine(lastFix.lat, lastFix.lon, lat, lon) > 5){
    lastFix = {lat, lon, t: Date.now()};
  }
  if (heading != null && !isNaN(heading) && heading >= 0 && spd != null && spd > MIN_SPEED){
    course = heading;
  }
  if (course == null) return; // stationary or no course: hold last heading
  if (lastHeading == null){
    lastHeading = course;
  } else {
    // Smooth jitter, handling wrap-around at 0/360
    const diff = ((course - lastHeading + 540) % 360) - 180;
    lastHeading = (lastHeading + diff * 0.3 + 360) % 360;
  }
}

function onFix(lat, lon, heading, speed){
  if (!isHidden()) updateHeading(lat, lon, heading, speed);
  updateMyMarker(lat, lon);
  if (!isHidden()) applyBearing();
  queueSend(lat, lon);
}

// Outbound throttle: send now if 7 s passed or moved >= 15 m, else send the latest fix when 7 s is up
function queueSend(lat, lon){
  pendingFix = {lat, lon, ts: Date.now()};
  const now = Date.now();
  const moved = lastSent ? haversine(lastSent.lat, lastSent.lon, lat, lon) : Infinity;
  if (moved >= SEND_DISTANCE_M || now - lastSendAt >= SEND_INTERVAL_MS || !lastSent){
    flushPos();
  } else if (!sendTimer){
    sendTimer = setTimeout(flushPos, SEND_INTERVAL_MS - (now - (lastSent ? lastSent.t : 0)));
  }
}
function flushPos(){
  if (sendTimer){ clearTimeout(sendTimer); sendTimer = null; }
  if (!pendingFix) return;
  const f = pendingFix; pendingFix = null;
  lastSent = {lat: f.lat, lon: f.lon, t: Date.now()};
  if (!wsSend({type:'pos', lat:f.lat, lon:f.lon, ts:f.ts})){
    posQueue.push(f);
    if (posQueue.length > MAX_QUEUE) posQueue.shift();
  }
}
function wsSend(obj){
  if (ws && ws.readyState === 1 && joined){
    ws.send(JSON.stringify(obj));
    lastSendAt = Date.now();
    return true;
  }
  return false;
}
let joined = false;

// Selecting yourself ("me": the blank -- Riders -- entry or your own YOU marker)
// clears any selected rider: dropdown value, Find target/line, open rider popup.
function clearRiderSelection(){
  const sel = document.getElementById('riderList');
  if (sel) sel.value = '';
  if (findTarget) clearFindLine();
  clearRampRoute();
  document.getElementById('findBtn').style.display = 'none';
  const hasOthers = Object.keys(positions).some(k => k !== me);
  document.getElementById('msgBox').style.display = hasOthers ? 'flex' : 'none';
  for (const k in riders){ if (k !== me && riders[k].closePopup) riders[k].closePopup(); }
}

function onRiderSelect(){
  const sel = document.getElementById('riderList');
  const id = sel.value;
  if (!id){ clearRiderSelection(); return; }
  document.getElementById('msgBox').style.display = 'flex';
  document.getElementById('findBtn').style.display = 'inline-block';
  if (id && positions[id]){
    setFollow(false);
    map.panTo([positions[id].lat, positions[id].lon]);
  }
  if (findTarget && findTarget !== id) clearFindLine();
  clearRampRoute();
}

function toggleFind(){
  const sel = document.getElementById('riderList');
  const id = sel.value;
  if (!id || !myLatLng || !positions[id]) return;
  if (findTarget === id){
    clearFindLine();
    return;
  }
  clearRampRoute();
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
  const others = [];
  for (const id in positions){
    if (id === me) continue;
    const p = positions[id];
    const dist = myLatLng ? haversine(myLatLng[0], myLatLng[1], p.lat, p.lon) : null;
    others.push({id, name: p.leader ? '★ ' + p.name + ' (Leader)' : p.name, dist});
  }
  others.sort((a,b) => (a.dist == null || b.dist == null) ? a.name.localeCompare(b.name) : a.dist - b.dist);
  const key = (leader ? 'L|' : '') + others.map(o => o.id + ':' + o.name + ':' + (o.dist == null ? '-' : Math.round(o.dist))).join('|');
  if (key === lastListKey) return;
  lastListKey = key;

  const current = sel.value;
  sel.innerHTML = '<option value="">-- Riders --</option>';
  others.forEach(o => {
    const opt = document.createElement('option');
    opt.value = o.id;
    opt.textContent = o.dist == null ? o.name : `${o.name} (${(o.dist / 1609.34).toFixed(2)} mi)`;
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
  breadcrumbPending.push([lat, lon]);
  if (breadcrumbPending.length > MAX_BREADCRUMB) breadcrumbPending.shift();
  if (isHidden()) return; // background: no drawing at all
  renderMe();
}

let breadcrumbPending = [];
function renderMe(){
  if (!myLatLng) return;
  // Breadcrumb trail (fixes collected while hidden are added on return)
  breadcrumbPending.forEach(p => breadcrumb.push(p));
  breadcrumbPending = [];
  while (breadcrumb.length > MAX_BREADCRUMB) breadcrumb.shift();
  if (breadcrumbLine){
    breadcrumbLine.setLatLngs(breadcrumb);
  } else if (breadcrumb.length > 1){
    breadcrumbLine = L.polyline(breadcrumb, {
      color: '#22c55e',
      weight: 4,
      opacity: 0.7
    }).addTo(map);
  }

  if (riders[me]){
    riders[me].setLatLng(myLatLng);
  } else {
    const icon = L.divIcon({
      className: '',
      html: `<div class="me-arrow" style="width:22px;height:22px;transform-origin:50% 50%;"><div style="
        width:0;height:0;
        border-left:11px solid transparent;
        border-right:11px solid transparent;
        border-bottom:22px solid #000;
        position:relative;
      ">
        <div style="
          position:absolute;
          top:2px;left:-9px;
          width:0;height:0;
          border-left:9px solid transparent;
          border-right:9px solid transparent;
          border-bottom:18px solid #e11d48;
        "></div>
        <div style="
          position:absolute;
          top:4px;left:-12px;
          width:24px;text-align:center;
          color:#fff;font-weight:900;font-size:8px;
          text-shadow:0 0 2px #000;
        ">YOU</div>
      </div></div>`,
      iconSize:[22,22],
      iconAnchor:[11,11]
    });
    riders[me] = L.marker(myLatLng,{icon, zIndexOffset:2000}).addTo(map).bindPopup(myName + ' (you)');
    riders[me].on('click', () => clearRiderSelection());
    rotateMe();
  }
  if (followMe) map.panTo(myLatLng);
  rotateMe();
  updateFindLine();
  updateRampRoute();
  renderDirty = true; // rider list (distances) refreshed by the 1 s render loop
}

function connect(){
  if (reconnectTimer){ clearTimeout(reconnectTimer); reconnectTimer = null; }
  if (ws && (ws.readyState === 0 || ws.readyState === 1)) return;
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  joined = false;
  ws = new WebSocket(proto + '://' + location.host + '/ws');
  ws.onopen = () => {
    status('Connected');
    ws.send(JSON.stringify({
      type: 'join',
      id: me,
      name: myName,
      code: myGroup,
      leader: leader
    }));
    lastSendAt = Date.now();
    // Keep-alive only when nothing else has been sent for a while; positions double as keep-alive
    if (pingTimer) clearInterval(pingTimer);
    pingTimer = setInterval(() => {
      if (Date.now() - lastSendAt >= KEEPALIVE_MS) wsSend({type:'ping'});
    }, 5000);
  };
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.type === 'joined'){
      joined = true;
      reconnectDelay = 1000; // reset backoff on success
      status('Sharing — ' + myGroup);
      // Send positions queued while offline, oldest first; server keeps the newest
      if (posQueue.length){
        wsSend({type:'posbatch', positions: posQueue});
        posQueue = [];
      }
      if (pendingFix) flushPos();
      if (myLatLng && !isHidden()) renderMe();
    }
    else if (m.type === 'error'){ status(m.msg); }
    else if (m.type === 'riders'){
      if (isHidden()) return; // background: ignore others, resync on return
      m.riders.forEach(r => { pendingRiders[r.id] = r; });
      renderDirty = true;
    }
    else if (m.type === 'pos') {
      if (isHidden()) return;
      pendingRiders[m.id] = m;
      renderDirty = true;
    }
    else if (m.type === 'alert'){
      if (m.id === me) return;
      if (positions[m.id]){ positions[m.id].stale = true; setRiderStale(m.id, true); }
      const mins = Math.max(1, Math.round((Date.now()/1000 - m.lastSeen) / 60));
      showAlert('⚠ ' + (m.name || 'A rider') + ' has gone quiet — last seen ' + mins + ' min ago');
    }
    else if (m.type === 'recovered'){
      if (m.id === me) return;
      if (positions[m.id]){ positions[m.id].stale = false; setRiderStale(m.id, false); }
      if (!isHidden()) status((m.name || 'Rider') + ' is back');
    }
    else if (m.type === 'leader'){
      if (m.id === me) return;
      if (positions[m.id]){ positions[m.id].leader = !!m.on; setRiderStale(m.id, positions[m.id].stale); }
      if (pendingRiders[m.id]) pendingRiders[m.id].leader = !!m.on;
      lastListKey = ''; updateRiderList();
    }
    else if (m.type === 'leave') remove(m.id);
    else if (m.type === 'msg'){
      const txt = (m.from || 'Someone') + ': ' + m.text;
      showBanner(txt, m.fromId);
    }
  };
  ws.onclose = () => {
    joined = false;
    if (pingTimer) clearInterval(pingTimer);
    if (sharing) scheduleReconnect();
  };
}
// Exponential backoff: 1 s, 2 s, 4 s ... capped at 60 s; reset on a successful join
function scheduleReconnect(){
  if (reconnectTimer) return;
  status('Reconnecting in ' + Math.round(reconnectDelay/1000) + 's...');
  reconnectTimer = setTimeout(() => { reconnectTimer = null; connect(); }, reconnectDelay);
  reconnectDelay = Math.min(reconnectDelay * 2, 60000);
}

function showAlert(text){
  const b = document.getElementById('banner');
  b.classList.add('alert');
  showBanner(text, null);
  setTimeout(() => b.classList.remove('alert'), BANNER_MS);
  if (navigator.vibrate) { try { navigator.vibrate([300, 150, 300]); } catch(e){} }
}

// Leader = purple dot (#8b5cf6) with dark outline and a star; stale leader stays grey
// but keeps the purple outline + star so it is still identifiable
function riderInitial(name){
  const c = String(name || '').trim().charAt(0);
  return c ? c.toUpperCase() : '?';
}
function escHtml(t){
  return String(t).replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
}
function riderIcon(stale, isLeader, name){
  const bg = isLeader ? (stale ? '#9ca3af' : '#8b5cf6') : (stale ? '#9ca3af' : '#4aa3ff');
  const op = stale ? (isLeader ? 0.8 : 0.6) : 1;
  const border = isLeader ? `3px solid ${stale ? '#8b5cf6' : '#1e1b4b'}` : '2px solid #fff';
  const badge = isLeader ? `<div style="
      position:absolute;top:-6px;right:-6px;width:14px;height:14px;border-radius:50%;
      background:#fbbf24;border:1px solid #fff;color:#fff;font-size:10px;line-height:14px;
      text-align:center;box-shadow:0 0 3px rgba(0,0,0,.5);">★</div>` : '';
  return L.divIcon({
    className: '',
    html: `<div style="position:relative;width:28px;height:28px;">
      <div style="
        box-sizing:border-box;width:28px;height:28px;border-radius:50%;
        background:${bg};opacity:${op};border:${border};
        box-shadow:0 1px 4px rgba(0,0,0,.45);
        color:#fff;font:bold 14px/1 -apple-system,system-ui,sans-serif;
        display:flex;align-items:center;justify-content:center;
      ">${escHtml(riderInitial(name))}</div>${badge}</div>`,
    iconSize:[28,28],
    iconAnchor:[14,14],
    popupAnchor:[0,-14]
  });
}
function riderPopup(id){
  const p = positions[id];
  if (!p) return '';
  const nm = p.leader ? '★ ' + p.name + ' (Leader)' : p.name;
  if (p.stale) {
    const mins = Math.max(1, Math.round((Date.now() - (lastSeen[id] || Date.now())) / 60000));
    return nm + ' (last seen ' + mins + ' min ago)';
  }
  return nm;
}
function setRiderStale(id, stale){
  if (!riders[id] || id === me) return;
  riders[id].setIcon(riderIcon(stale, positions[id] && positions[id].leader, positions[id] && positions[id].name));
  riders[id].setPopupContent(riderPopup(id));
}

// Render loop: apply batched rider updates at most once a second, never while hidden
setInterval(() => {
  if (isHidden() || !renderDirty) return;
  renderDirty = false;
  for (const id in pendingRiders){
    upsert(pendingRiders[id]);
    delete pendingRiders[id];
  }
  updateRiderList();
}, 1000);

function upsert(r){
  if (r.lat == null && r.lon == null) return;
  if (r.id === me) return; // my own marker comes from local GPS only
  const name = r.name || 'Rider';
  const age = (typeof r.age === 'number') ? r.age * 1000 : 0;
  lastSeen[r.id] = Date.now() - age;
  const stale = !!r.stale || age > STALE_MS;
  const wasStale = positions[r.id] && positions[r.id].stale;
  const wasLeader = positions[r.id] && positions[r.id].leader;
  const wasName = positions[r.id] && positions[r.id].name;
  const isLeader = !!r.leader;
  positions[r.id] = {lat: r.lat, lon: r.lon, name, stale, leader: isLeader};
  if (riders[r.id]){
    riders[r.id].setLatLng([r.lat, r.lon]);
    if (wasStale !== stale || wasLeader !== isLeader || wasName !== name) riders[r.id].setIcon(riderIcon(stale, isLeader, name));
    riders[r.id].setPopupContent(riderPopup(r.id));
  } else {
    riders[r.id] = L.marker([r.lat, r.lon],{icon: riderIcon(stale, isLeader, name), zIndexOffset: isLeader ? 1000 : 0}).addTo(map).bindPopup(riderPopup(r.id));
    const rid = r.id;
    riders[rid].on('click', () => selectRiderFromMap(rid));
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

// Silent riders are greyed out with 'last seen', not removed; forget them after 30 min
setInterval(() => {
  if (isHidden()) return;
  const now = Date.now();
  for (const id in lastSeen){
    if (id === me) continue;
    const age = now - lastSeen[id];
    if (age > REMOVE_MS) remove(id);
    else if (age > STALE_MS && positions[id] && !positions[id].stale){
      positions[id].stale = true; setRiderStale(id, true);
    }
  }
}, 15000);

// Browser location watch (non-Capacitor): restartable, since iPhone Safari
// can stop delivering watchPosition after the page is backgrounded.
let lastFixAt = 0, lastWebRestart = 0, webRestartTimer = null;
function webFix(p){
  lastFixAt = Date.now();
  onFix(p.coords.latitude, p.coords.longitude, p.coords.heading, p.coords.speed); // throttled send happens in onFix
}
function startWebWatch(){
  if (isNativeApp() || !navigator.geolocation) return;
  if (watchId !== null){ try { navigator.geolocation.clearWatch(watchId); } catch(_){} }
  lastWebRestart = Date.now();
  lastFixAt = Date.now(); // grace period before the watchdog fires again
  watchId = navigator.geolocation.watchPosition(webFix, e => {
    status('Location error: ' + e.message);
    if (e.code === 2 || e.code === 3) scheduleWebRestart();
  }, {enableHighAccuracy:true, maximumAge:10000, timeout:20000});
}
function scheduleWebRestart(){
  if (webRestartTimer) return;
  const wait = Math.max(2000, 5000 - (Date.now() - lastWebRestart));
  webRestartTimer = setTimeout(() => { webRestartTimer = null; if (sharing) startWebWatch(); }, wait);
}
setInterval(() => {
  if (sharing && !isNativeApp() && document.visibilityState === 'visible' && Date.now() - lastFixAt > 30000) startWebWatch();
}, 10000);

document.addEventListener('visibilitychange', () => {
  if (!sharing) return;
  if (document.visibilityState === 'visible') {
    if (!ws || ws.readyState !== 1) {
      reconnectDelay = 1000;
      if (reconnectTimer){ clearTimeout(reconnectTimer); reconnectTimer = null; }
      setTimeout(connect, 500); // 'riders' snapshot arrives after join
    } else {
      wsSend({type:'sync'}); // one fresh snapshot, rendered once
    }
    renderMe();
    applyBearing();
    requestWakeLock();
    if (!isNativeApp() && navigator.geolocation){
      startWebWatch();
      navigator.geolocation.getCurrentPosition(webFix, () => {}, {enableHighAccuracy:true, maximumAge:0, timeout:15000});
    }
  }
});

// Screen wake lock: only for the group leader, and only inside the native app
let leader = localStorage.getItem('trackerLeader') === '1';
let wakeLock = null;
function isNativeApp(){ return !!(window.Capacitor && window.Capacitor.isNativePlatform && window.Capacitor.isNativePlatform()); }
function updateLeaderBtn(){
  const b = document.getElementById('leaderBtn');
  b.classList.toggle('on', leader);
  b.textContent = leader ? 'Leader ✓' : 'Leader';
}
function toggleLeader(){
  leader = !leader;
  localStorage.setItem('trackerLeader', leader ? '1' : '0');
  updateLeaderBtn();
  if (ws && ws.readyState === 1 && joined) wsSend({type:'leader', on: leader}); // tell the group in real time
  if (leader) requestWakeLock(); else releaseWakeLock();
  if (leader && !isNativeApp()) status('Leader on (screen stays awake only in the app)');
}
function requestWakeLock(){
  if (!leader || !isNativeApp() || !('wakeLock' in navigator) || !sharing) return;
  if (wakeLock && !wakeLock.released) return;
  navigator.wakeLock.request('screen').then(l => { wakeLock = l; }).catch(()=>{});
}
function releaseWakeLock(){
  if (wakeLock){ wakeLock.release().catch(()=>{}); wakeLock = null; }
}
updateLeaderBtn();

let myGroup = '';
function startApp(){
  const name = document.getElementById('startName').value.trim();
  if (!name){
    document.getElementById('startName').focus();
    return;
  }
  const grp = document.getElementById('startGroup').value;
  if (!grp){
    alert('Please select your group first.');
    document.getElementById('startGroup').focus();
    return;
  }
  myName = name;
  myGroup = grp;
  document.getElementById('groupDisplay').value = myGroup;
  document.getElementById('nameScreen').style.display = 'none';
  document.getElementById('map').style.display = 'block';
  document.getElementById('bar').style.display = 'flex';
  document.getElementById('status').style.display = 'block';
  document.getElementById('headingBtn').style.display = 'block';
  updateHeadingBtn();
  setFollow(true);
  setTimeout(() => {
    map.invalidateSize();
  }, 300);
  sharing = true;
  connect();
  requestWakeLock();

  // Prefer native background geolocation when running inside Capacitor
  if (window.Capacitor && window.Capacitor.Plugins && window.Capacitor.Plugins.BackgroundGeolocation){
    const BackgroundGeolocation = window.Capacitor.Plugins.BackgroundGeolocation;
    BackgroundGeolocation.addWatcher(
      {
        backgroundMessage: "Tracking your location for " + myGroup,
        backgroundTitle: "Water Tracker",
        requestPermissions: true,
        stale: false,
        distanceFilter: 15  // ~15 m; no significant-change mode (too coarse for riders)
      },
      function callback(location, error){
        if (error){
          if (error.code === "NOT_AUTHORIZED"){
            status("Location permission denied");
          }
          return;
        }
        const lat = location.latitude;
        const lon = location.longitude;
        onFix(lat, lon, location.bearing, location.speed); // throttled send happens in onFix
      }
    ).then(function(id){
      watchId = id;
    });
  } else {
    // Fallback for browser / non-Capacitor
    startWebWatch();
  }
}


// ---- Boat ramps & marinas (OpenStreetMap via server /api/ramps) ----
let rampLayer = null, rampsOn = false, rampsLoading = false, rampToastTimer = null;
function rampToast(t){
  const el = document.getElementById('rampToast');
  el.textContent = t; el.style.display = 'block';
  clearTimeout(rampToastTimer); rampToastTimer = setTimeout(() => el.style.display = 'none', 4000);
}
function rampEsc(t){ return String(t).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function rampMiles(a, b, c, d){
  const R = 3958.8, r = x => x * Math.PI / 180;
  const h = Math.sin(r(c-a)/2)**2 + Math.cos(r(a))*Math.cos(r(c))*Math.sin(r(d-b)/2)**2;
  return 2 * R * Math.asin(Math.sqrt(h));
}
function rampDirUrl(lat, lon){
  const ios = /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  return ios ? ('https://maps.apple.com/?daddr=' + lat + ',' + lon)
             : ('https://www.google.com/maps/dir/?api=1&destination=' + lat + ',' + lon);
}
async function toggleRamps(){
  const btn = document.getElementById('rampsBtn');
  if (rampsOn) {
    if (rampLayer) { map.removeLayer(rampLayer); rampLayer = null; }
    clearRampRoute(); rampItems = [];
    rampsOn = false; btn.classList.remove('on'); btn.textContent = 'Ramps';
    return;
  }
  if (rampsLoading) return;
  const c = myLatLng || [map.getCenter().lat, map.getCenter().lng];
  rampsLoading = true; btn.textContent = 'Loading…'; btn.disabled = true;
  const ctrl = new AbortController();
  const rampTimer = setTimeout(() => ctrl.abort(), 20000);
  try {
    const r = await fetch('/api/ramps?lat=' + c[0].toFixed(5) + '&lon=' + c[1].toFixed(5), {signal: ctrl.signal});
    if (!r.ok) throw new Error('http ' + r.status);
    const data = await r.json();
    const items = data.results || [];
    if (!items.length) { rampToast('No ramps or marinas found nearby'); return; }
    rampLayer = L.layerGroup();
    rampItems = items;
    items.forEach((it, i) => {
      const marina = it.type === 'marina';
      const icon = L.divIcon({className:'', html:'<div class="rampIcon' + (marina ? ' marina' : '') + '">' + (marina ? '⚓' : '🚤') + '</div>', iconSize:[26,26], iconAnchor:[13,13]});
      const m = L.marker([it.lat, it.lon], {icon, zIndexOffset:-500});
      m.bindPopup(() => {
        const from = myLatLng || c;
        const mi = rampMiles(from[0], from[1], it.lat, it.lon);
        return '<b>' + rampEsc(it.name) + '</b><br>' + (marina ? 'Marina' : 'Boat ramp') + ' · ' + mi.toFixed(1) + ' mi ' + (myLatLng ? 'from you' : 'away') +
          '<br><a href="' + rampDirUrl(it.lat, it.lon) + '" target="_blank" rel="noopener">Directions</a>' +
          ' · <a href="#" onclick="toggleRampRoute(' + i + ');return false;">' + (rampRoute === it ? 'Clear route' : 'Route') + '</a>' +
          '<br><small>© OpenStreetMap contributors</small>';
      });
      rampLayer.addLayer(m);
    });
    rampLayer.addTo(map);
    rampsOn = true; btn.classList.add('on');
    rampToast(items.length + ' ramps/marinas nearby · © OpenStreetMap contributors');
  } catch (e) {
    rampToast("Couldn't reach map data, check cell signal");
  } finally {
    clearTimeout(rampTimer);
    rampsLoading = false; btn.disabled = false; btn.textContent = rampsOn ? 'Hide Ramps' : 'Ramps';
  }
}
</script>
</body>
</html>"""

# ---- Boat ramps & marinas (OpenStreetMap / Overpass) ----
import math, urllib.request, urllib.parse
from fastapi.responses import JSONResponse
OVERPASS_URLS = [
    ("https://overpass-api.de/api/interpreter", 25),
    ("https://overpass.kumi.systems/api/interpreter", 15),
    ("https://maps.mail.ru/osm/tools/overpass/api/interpreter", 15),
]
RAMP_CACHE_SECS = 24 * 3600
ramp_cache = {}  # key -> (timestamp, raw elements)

def _miles(a, b, c, d):
    r = math.radians
    h = math.sin(r(c - a) / 2) ** 2 + math.cos(r(a)) * math.cos(r(c)) * math.sin(r(d - b) / 2) ** 2
    return 2 * 3958.8 * math.asin(math.sqrt(h))

def _overpass_fetch(lat, lon, radius_m):
    q = (f"[out:json][timeout:25];(nwr[leisure=slipway](around:{radius_m},{lat},{lon});"
         f"nwr[leisure=marina](around:{radius_m},{lat},{lon}););out center tags;")
    body = urllib.parse.urlencode({"data": q}).encode()
    errs = []
    for url, tmo in OVERPASS_URLS:
        try:
            req = urllib.request.Request(url, data=body, headers={"User-Agent": "WaterTracker/1.0 (github.com/jlegacy/water-tracker)", "Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"})
            with urllib.request.urlopen(req, timeout=tmo) as r:
                return json.loads(r.read().decode()).get("elements", [])
        except Exception as e:
            errs.append(f"{url.split('/')[2]}: {type(e).__name__} {e}"[:200])
    print("overpass failed:", errs, flush=True)
    raise RuntimeError("; ".join(errs))

# Bundled NC data (built by scripts/build_ramps.py from Geofabrik's OSM extract)
NC_BBOX = (33.75, -84.33, 36.60, -75.40)  # south, west, north, east
try:
    _rd = json.loads((pathlib.Path(__file__).parent / "data" / "nc_ramps.json").read_text())
    LOCAL_RAMPS = _rd.get("items", [])
    print(f"loaded {len(LOCAL_RAMPS)} local ramps/marinas (generated {_rd.get('generated')})", flush=True)
except Exception as e:
    LOCAL_RAMPS = []
    print("local ramps data unavailable:", e, flush=True)

def _in_nc(lat, lon):
    s, w, n, e = NC_BBOX
    return s <= lat <= n and w <= lon <= e

@app.get("/api/ramps")
async def api_ramps(lat: float, lon: float, radius_km: float = 40):
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return JSONResponse({"error": "bad coordinates"}, status_code=400)
    radius_km = max(1.0, min(float(radius_km), 80.0))
    radius_mi = radius_km / 1.609344
    local = []
    for it in LOCAL_RAMPS:
        d = _miles(lat, lon, it["lat"], it["lon"])
        if d <= radius_mi:
            local.append({"type": it["type"], "name": it["name"] or ("Marina" if it["type"] == "marina" else "Boat ramp"),
                          "lat": it["lat"], "lon": it["lon"], "distance_mi": round(d, 1)})
    if local or _in_nc(lat, lon):
        local.sort(key=lambda x: x["distance_mi"])
        return {"results": local[:100], "count": min(len(local), 100), "stale": False, "source": "local",
                "attribution": "© OpenStreetMap contributors"}
    # Outside NC with no bundled data: fall back to live Overpass
    clat, clon = round(lat, 1), round(lon, 1)
    key = (clat, clon, round(radius_km))
    now = time.time()
    hit = ramp_cache.get(key)
    stale = False
    if hit and now - hit[0] < RAMP_CACHE_SECS:
        elements = hit[1]
    else:
        try:
            elements = await asyncio.to_thread(_overpass_fetch, clat, clon, int(radius_km * 1000))
            ramp_cache[key] = (now, elements)
        except Exception as e:
            last_err = str(e)
            if hit:
                elements, stale = hit[1], True
            else:
                return JSONResponse({"error": "Couldn't reach map data right now. Check cell signal and try again.", "detail": last_err}, status_code=503)
    out, seen = [], set()
    for el in elements:
        t = el.get("tags", {})
        elat = el.get("lat", (el.get("center") or {}).get("lat"))
        elon = el.get("lon", (el.get("center") or {}).get("lon"))
        if elat is None or elon is None:
            continue
        kind = "marina" if t.get("leisure") == "marina" else "ramp"
        k = (el.get("type"), el.get("id"))
        if k in seen:
            continue
        seen.add(k)
        out.append({"type": kind, "name": t.get("name") or ("Marina" if kind == "marina" else "Boat ramp"),
                    "lat": elat, "lon": elon, "distance_mi": round(_miles(lat, lon, elat, elon), 1)})
    out.sort(key=lambda x: x["distance_mi"])
    return {"results": out[:100], "count": min(len(out), 100), "stale": stale,
            "attribution": "© OpenStreetMap contributors"}

@app.get("/")
async def index():
    return HTMLResponse(INDEX_HTML)

@app.get("/manifest.json")
async def manifest():
    return FileResponse(pathlib.Path(__file__).parent / "manifest.json", media_type="application/manifest+json")

ICON_FILES = ("icon-192.png", "icon-512.png", "icon-maskable-512.png", "apple-touch-icon.png")

for _icon in ICON_FILES:
    def _make(fn):
        async def _serve():
            return FileResponse(pathlib.Path(__file__).parent / fn, media_type="image/png")
        return _serve
    app.get("/" + _icon)(_make(_icon))

@app.on_event("startup")
async def startup():
    asyncio.create_task(periodic_broadcast())
    asyncio.create_task(stale_monitor())

async def stale_monitor():
    """Mark riders silent for STALE_SECS as stale and alert their group once; purge after PURGE_SECS."""
    while True:
        await asyncio.sleep(STALE_CHECK_SECS)
        try:
            await check_stale()
        except Exception:
            pass

async def check_stale():
    now = time.time()
    for code in list(groups.keys()):
        g = groups.get(code, {})
        for rid, r in list(g.items()):
            age = now - r["updated"]
            if age > PURGE_SECS and r.get("ws") is None:
                g.pop(rid, None)
                await broadcast(code, {"type": "leave", "id": rid})
                continue
            if r["lat"] is not None and age > STALE_SECS and not r.get("stale"):
                r["stale"] = True
                await broadcast(code, {"type": "alert", "id": rid, "name": r["name"],
                                       "lastSeen": r["updated"]})
                # TODO(push): also send APNs/FCM push to the group's registered devices here.
        if not g:
            groups.pop(code, None)

async def mark_fresh(code, rid):
    r = groups.get(code, {}).get(rid)
    if r and r.get("stale"):
        r["stale"] = False
        await broadcast(code, {"type": "recovered", "id": rid, "name": r["name"]})

def apply_pos(r, lat, lon, ts):
    """Apply a position if it is newer than what we have (ts in ms, optional for old clients)."""
    if ts is not None:
        try:
            ts = float(ts)
        except (TypeError, ValueError):
            ts = None
    if ts is not None and r.get("ts") is not None and ts <= r["ts"]:
        return False  # older than current: ignore
    r["lat"] = float(lat)
    r["lon"] = float(lon)
    r["ts"] = ts
    return True

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
        code = GROUP_BY_UPPER.get(" ".join(str(msg.get("code") or "").split()).upper())
        if not code:
            await ws.send_text(json.dumps({"type": "error", "msg": "Unknown group"}))
            await ws.close()
            return
        if code not in groups:
            groups[code] = {}
        prev = groups[code].get(rider_id)
        if prev:  # rejoin after a drop: keep last known position
            prev.update({"name": name, "ws": ws, "leader": bool(msg.get("leader"))})
        else:
            groups[code][rider_id] = {"name": name, "lat": None, "lon": None, "ts": None,
                                      "updated": time.time(), "ws": ws, "stale": False,
                                      "leader": bool(msg.get("leader"))}
        await ws.send_text(json.dumps({"type": "joined", "id": rider_id, "code": code}))
        await broadcast(code, {"type": "riders", "riders": public_list(code)})

        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            t = msg.get("type")
            g = groups.get(code, {})
            if rider_id in g:
                g[rider_id]["updated"] = time.time()  # any message counts as keep-alive
                if g[rider_id].get("ws") is not ws:
                    g[rider_id]["ws"] = ws
                await mark_fresh(code, rider_id)
            if t in ("pos", "posbatch"):
                if rider_id in g:
                    r = g[rider_id]
                    items = [msg] if t == "pos" else (msg.get("positions") or [])[-50:]
                    changed = False
                    for p in sorted(items, key=lambda p: p.get("ts") or 0):
                        try:
                            changed = apply_pos(r, p["lat"], p["lon"], p.get("ts")) or changed
                        except (KeyError, TypeError, ValueError):
                            pass
                    if changed:
                        await broadcast(code, {"type": "pos", "id": rider_id,
                                        "name": r["name"], "lat": r["lat"], "lon": r["lon"],
                                        "ts": r.get("ts"), "leader": bool(r.get("leader"))})
            elif t == "leader":
                if rider_id in g:
                    g[rider_id]["leader"] = bool(msg.get("on"))
                    await broadcast(code, {"type": "leader", "id": rider_id,
                                           "on": g[rider_id]["leader"]})
            elif t == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))
            elif t == "sync":
                await ws.send_text(json.dumps({"type": "riders", "riders": public_list(code)}))
            elif t == "leave":
                g.pop(rider_id, None)
                await broadcast(code, {"type": "leave", "id": rider_id})
                rider_id = None
                break
            elif t == "msg":
                to_id = msg.get("to")
                text = (msg.get("text") or "").strip()[:200]
                if to_id and text and code in groups and to_id in groups[code]:
                    target = groups[code][to_id]
                    if target.get("ws") is None:
                        continue
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
                        if rid == rider_id or r.get("ws") is None:
                            continue
                        try:
                            await r["ws"].send_text(payload)
                        except Exception:
                            pass
    except WebSocketDisconnect:
        pass
    finally:
        # A dropped connection is not a leave: keep the rider so the group can see
        # 'last seen' and get a stale alert. Explicit 'leave' or the 30 min purge removes them.
        if rider_id and code:
            r = groups.get(code, {}).get(rider_id)
            if r and r.get("ws") is ws:
                r["ws"] = None
                if r["lat"] is None:
                    groups[code].pop(rider_id, None)
                    if not groups[code]:
                        groups.pop(code, None)

def public_list(code):
    now = time.time()
    out = []
    for rid, r in groups.get(code, {}).items():
        if r["lat"] is None:
            continue
        out.append({"id": rid, "name": r["name"], "lat": r["lat"],
                    "lon": r["lon"], "age": round(now - r["updated"], 1),
                    "stale": bool(r.get("stale")), "leader": bool(r.get("leader"))})
    return out

async def broadcast(code, msg):
    payload = json.dumps(msg)
    dead = []
    for rid, r in list(groups.get(code, {}).items()):
        if r.get("ws") is None:
            continue
        try:
            await r["ws"].send_text(payload)
        except Exception:
            dead.append(rid)
    for rid in dead:  # keep the rider (for stale/last-seen), just drop the dead socket
        r = groups.get(code, {}).get(rid)
        if r:
            r["ws"] = None
