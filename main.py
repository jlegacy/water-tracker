from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
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
from fastapi.staticfiles import StaticFiles
app.mount("/static", StaticFiles(directory=pathlib.Path(__file__).parent / "static"), name="static")

WWW_DIR = pathlib.Path(__file__).parent / "water-tracker-app" / "www"

# Allow Capacitor shells (capacitor:// / ionic:// / localhost) to call API when UI is local.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# One shared world, no groups: riders see everyone within RANGE_MI of them.
riders = {}   # rider_id -> {name, lat, lon, ts, updated, ws, stale, leader, sos}
links = set() # (viewer, subject): viewer currently sees subject (directed; ranges differ per rider)
RANGE_MI = float(os.environ.get("RANGE_MI", "25"))       # default viewing range (old clients)
HIDE_PAD_MI = float(os.environ.get("HIDE_PAD_MI", "2"))  # hysteresis: only hide past range + pad
HIDE_MI = RANGE_MI + HIDE_PAD_MI
ALLOWED_RANGES = (25, 30, 35, 40, 45, 50)

def valid_range(v):
    """Clamp a client-sent range to the allowed set; anything else -> default."""
    try:
        v = int(float(v))
    except (TypeError, ValueError):
        return int(RANGE_MI)
    return v if v in ALLOWED_RANGES else int(RANGE_MI)

# ---- Rider marker style (color + icon) ----
# PREMIUM-GATE: rider styles are free for now; gate here (force defaults) if premium returns.
# Colors exclude SOS red and leader purple. "default" = classic blue (others) / teal (you).
STYLE_COLORS = ("default", "blue", "sky", "teal", "green", "lime", "yellow", "orange", "brown", "slate")
STYLE_ICONS = ("initial", "boat", "wave", "anchor", "flag", "pirate", "dolphin", "shark", "fish")

def valid_color(v):
    return v if isinstance(v, str) and v in STYLE_COLORS else "default"

def valid_icon(v):
    return v if isinstance(v, str) and v in STYLE_ICONS else "initial"

# ---- Boat ramps & marinas (OpenStreetMap / Overpass) ----
import math, sys, urllib.request, urllib.parse
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

# Bundled East Coast data (built by scripts/build_ramps.py from Geofabrik's OSM extracts)
# Compact rows [type(0=ramp,1=marina), name, lat, lon, state], indexed in 0.5-degree grid cells.
LOCAL_BBOXES = {}
RAMP_GRID = {}
LOCAL_COUNT = 0
try:
    _rd = json.loads((pathlib.Path(__file__).parent / "data" / "ramps_us.json").read_text())
    LOCAL_BBOXES = {k: tuple(v) for k, v in _rd.get("regions", {}).items()}
    for _r in _rd.get("items", []):
        RAMP_GRID.setdefault((int(_r[2] // 0.5), int(_r[3] // 0.5)), []).append(
            ("marina" if _r[0] else "ramp", sys.intern(_r[1]) if _r[1] else "", _r[2], _r[3]))
        LOCAL_COUNT += 1
    del _rd
    print(f"loaded {LOCAL_COUNT} local ramps/marinas for {','.join(LOCAL_BBOXES)}", flush=True)
except Exception as e:
    print("local ramps data unavailable:", e, flush=True)

def _in_local_region(lat, lon):
    return any(s <= lat <= n and w <= lon <= e for s, w, n, e in LOCAL_BBOXES.values())

@app.post("/api/leave")
async def api_leave(request: Request):
    # sendBeacon backup for a closing tab: remove only this rider id (any 'group' field is ignored)
    try:
        data = json.loads(await request.body() or b"{}")
    except Exception:
        return {"ok": False}
    if not isinstance(data, dict):
        return {"ok": False}
    rid = str(data.get("id") or "")
    if rid not in riders:
        return {"ok": False}
    await drop_rider(rid)
    return {"ok": True}

@app.get("/api/ramps")
async def api_ramps(lat: float, lon: float, radius_km: float = 40):
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return JSONResponse({"error": "bad coordinates"}, status_code=400)
    radius_km = max(1.0, min(float(radius_km), 80.0))
    radius_mi = radius_km / 1.609344
    local = []
    gy, gx = int(lat // 0.5), int(lon // 0.5)
    for dy in range(-2, 3):  # 0.5 deg cells; radius up to 80 km
        for dx in range(-3, 4):
            for t, nm, ilat, ilon in RAMP_GRID.get((gy + dy, gx + dx), ()):
                d = _miles(lat, lon, ilat, ilon)
                if d <= radius_mi:
                    local.append({"type": t, "name": nm or ("Marina" if t == "marina" else "Boat ramp"),
                                  "lat": ilat, "lon": ilon, "distance_mi": round(d, 1)})
    if local or _in_local_region(lat, lon):
        local.sort(key=lambda x: x["distance_mi"])
        return {"results": local[:100], "count": min(len(local), 100), "stale": False, "source": "local",
                "attribution": "© OpenStreetMap contributors"}
    # Outside all bundled states with no local data: fall back to live Overpass
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
    return FileResponse(WWW_DIR / "index.html")

@app.get("/privacy")
async def privacy_page():
    """Public privacy policy (generated from PRIVACY.md by tools/build_privacy.py)."""
    return FileResponse(WWW_DIR / "privacy.html", media_type="text/html",
                        headers={"Cache-Control": "public, max-age=3600"})

@app.get("/ramps_us.json")
async def ramps_us_json():
    """Bundled ramp/marina extract for the web client (native apps load it from www/)."""
    f = WWW_DIR / "ramps_us.json"
    if not f.exists():
        f = pathlib.Path(__file__).parent / "data" / "ramps_us.json"
    return FileResponse(f, media_type="application/json",
                        headers={"Cache-Control": "public, max-age=86400"})

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
    for rid, r in list(riders.items()):
        age = now - r["updated"]
        if age > PURGE_SECS and r.get("ws") is None:
            await drop_rider(rid)
            continue
        if r["lat"] is not None and age > STALE_SECS and not r.get("stale"):
            r["stale"] = True
            await send_near(rid, {"type": "alert", "id": rid, "name": r["name"],
                                  "lastSeen": r["updated"]})
            # TODO(push): also send APNs/FCM push to nearby riders' registered devices here.

async def mark_fresh(rid):
    r = riders.get(rid)
    if r and r.get("stale"):
        r["stale"] = False
        await send_near(rid, {"type": "recovered", "id": rid, "name": r["name"]})

# ---- Per-rider viewing range (replaces groups) ----
def pair_in_range(dist_mi, shown, rng=None):
    """Hysteresis: appear at <= rng, and once shown stay until > rng + HIDE_PAD_MI."""
    rng = RANGE_MI if rng is None else rng
    return dist_mi <= rng or (shown and dist_mi <= rng + HIDE_PAD_MI)

def viewers(rid):
    """Riders who currently see rid (they receive rid's pos/SOS/leader/all/alerts)."""
    return [v for (v, s_) in links if s_ == rid and v in riders]

def seen_by(rid):
    """Riders rid currently sees (rid's list)."""
    return [s_ for (v, s_) in links if v == rid and s_ in riders]

neighbors = viewers  # back-compat name

def entry(rid, r, now=None):
    now = now or time.time()
    return {"id": rid, "name": r["name"], "lat": r["lat"], "lon": r["lon"],
            "age": round(now - r["updated"], 1), "stale": bool(r.get("stale")),
            "leader": bool(r.get("leader")), "sos": bool(r.get("sos")),
            "color": valid_color(r.get("color")), "icon": valid_icon(r.get("icon"))}

def update_links(rid):
    """Recompute both directions between rid and every other rider.
    Returns a list of (viewer, subject, added_bool) changes."""
    r = riders.get(rid)
    changes = []
    for oid, o in riders.items():
        if oid == rid:
            continue
        d = None
        if r is not None and r["lat"] is not None and o["lat"] is not None:
            d = _miles(r["lat"], r["lon"], o["lat"], o["lon"])
        for v, sub, vr in ((rid, oid, r), (oid, rid, o)):
            k = (v, sub)
            was = k in links
            now_in = d is not None and pair_in_range(d, was, (vr or {}).get("range", RANGE_MI))
            if now_in and not was:
                links.add(k); changes.append((v, sub, True))
            elif was and not now_in:
                links.discard(k); changes.append((v, sub, False))
    return changes

async def send_to(rid, msg):
    r = riders.get(rid)
    if not r or r.get("ws") is None:
        return
    try:
        await r["ws"].send_text(msg if isinstance(msg, str) else json.dumps(msg))
    except Exception:
        r["ws"] = None  # keep the rider (for stale/last-seen), just drop the dead socket

async def send_near(rid, msg, include_self=False):
    """Send to every rider whose own range currently includes rid."""
    payload = json.dumps(msg)
    targets = viewers(rid) + ([rid] if include_self else [])
    for oid in targets:
        await send_to(oid, payload)

async def apply_link_changes(changes):
    now = time.time()
    for v, sub, added in changes:
        if not added:
            await send_to(v, {"type": "leave", "id": sub})
        else:
            o = riders.get(sub)
            if o and o["lat"] is not None:
                await send_to(v, dict(entry(sub, o, now), type="pos"))

async def drop_rider(rid):
    for oid in viewers(rid):
        await send_to(oid, {"type": "leave", "id": rid})
    for k in [k for k in links if rid in k]:
        links.discard(k)
    riders.pop(rid, None)

def public_list(rid):
    """Snapshot for one viewer: only riders within that viewer's range."""
    now = time.time()
    return [entry(oid, riders[oid], now) for oid in seen_by(rid) if riders[oid]["lat"] is not None]

def new_rider(name, ws, leader=False, sos=False, rng=None, color=None, icon=None):
    return {"name": name, "lat": None, "lon": None, "ts": None, "updated": time.time(),
            "ws": ws, "stale": False, "leader": bool(leader), "sos": bool(sos),
            "range": valid_range(rng), "color": valid_color(color), "icon": valid_icon(icon)}


def sanitize_trail(raw, max_pts=60):
    """Cap and validate a thinned trail payload from a client (list of [lat, lon])."""
    if not isinstance(raw, list):
        return None
    out = []
    for pt in raw[-max_pts:]:
        try:
            if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                lat, lon = float(pt[0]), float(pt[1])
            elif isinstance(pt, dict) and "lat" in pt and "lon" in pt:
                lat, lon = float(pt["lat"]), float(pt["lon"])
            else:
                continue
            if abs(lat) > 90 or abs(lon) > 180:
                continue
            out.append([round(lat, 6), round(lon, 6)])
        except (TypeError, ValueError):
            continue
    return out

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
        for rid in list(riders.keys()):
            if rid in riders and riders[rid].get("ws") is not None:
                await send_to(rid, {"type": "riders", "riders": public_list(rid)})

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    rider_id = None
    try:
        raw = await ws.receive_text()
        msg = json.loads(raw)
        if msg.get("type") != "join":
            await ws.close()
            return
        rider_id = str(msg.get("id") or str(uuid.uuid4())[:8])
        name = (msg.get("name") or "Rider").strip()[:20] or "Rider"
        # Old clients may still send a group "code": accepted and ignored (one-release compat).
        my_range = valid_range(msg.get("range"))
        prev = riders.get(rider_id)
        if prev:  # rejoin after a drop: keep last known position
            prev.update({"name": name, "ws": ws, "leader": bool(msg.get("leader")),
                         "sos": bool(msg.get("sos")), "range": valid_range(msg.get("range")),
                         "color": valid_color(msg.get("color")), "icon": valid_icon(msg.get("icon"))})
            await apply_link_changes(update_links(rider_id))
        else:
            riders[rider_id] = new_rider(name, ws, msg.get("leader"), msg.get("sos"), msg.get("range"),
                                          msg.get("color"), msg.get("icon"))
        my_style = (riders[rider_id]["color"], riders[rider_id]["icon"])
        await ws.send_text(json.dumps({"type": "joined", "id": rider_id,
                                       "range": riders[rider_id]["range"], "ranges": list(ALLOWED_RANGES)}))
        await ws.send_text(json.dumps({"type": "riders", "riders": public_list(rider_id)}))

        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            t = msg.get("type")
            if t != "leave" and rider_id not in riders:
                # Removed by a /api/leave beacon while this socket is still alive: put the rider back.
                riders[rider_id] = new_rider(name, ws, rng=my_range, color=my_style[0], icon=my_style[1])
            r = riders.get(rider_id)
            if r:
                r["updated"] = time.time()  # any message counts as keep-alive
                if r.get("ws") is not ws:
                    r["ws"] = ws
                await mark_fresh(rider_id)
            if t in ("pos", "posbatch"):
                if r:
                    items = [msg] if t == "pos" else (msg.get("positions") or [])[-50:]
                    changed = False
                    for p in sorted(items, key=lambda p: p.get("ts") or 0):
                        try:
                            changed = apply_pos(r, p["lat"], p["lon"], p.get("ts")) or changed
                        except (KeyError, TypeError, ValueError):
                            pass
                    if changed:
                        await apply_link_changes(update_links(rider_id))
                        out = dict(entry(rider_id, r), type="pos", ts=r.get("ts"))
                        trail = sanitize_trail(msg.get("trail") if t == "pos" else None)
                        if trail and len(trail) >= 2:
                            out["trail"] = trail
                        await send_near(rider_id, out)
            elif t == "trail":
                pts = sanitize_trail(msg.get("points") if msg.get("points") is not None else msg.get("trail"))
                await send_near(rider_id, {"type": "trail", "id": rider_id, "points": pts or []})
            elif t == "style":
                if r:
                    r["color"], r["icon"] = valid_color(msg.get("color")), valid_icon(msg.get("icon"))
                    my_style = (r["color"], r["icon"])
                    await send_near(rider_id, {"type": "style", "id": rider_id, "color": r["color"], "icon": r["icon"]})
            elif t == "leader":
                if r:
                    r["leader"] = bool(msg.get("on"))
                    await send_near(rider_id, {"type": "leader", "id": rider_id, "on": r["leader"]})
            elif t == "sos":
                if r:
                    r["sos"] = bool(msg.get("on"))
                    await send_near(rider_id, {"type": "sos", "id": rider_id, "on": r["sos"]})
            elif t == "range":
                # Change my viewing range live (no rejoin)
                if r:
                    r["range"] = my_range = valid_range(msg.get("range"))
                    await apply_link_changes(update_links(rider_id))
                    await ws.send_text(json.dumps({"type": "range", "range": r["range"]}))
                    await ws.send_text(json.dumps({"type": "riders", "riders": public_list(rider_id)}))
            elif t == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))
            elif t == "sync":
                await ws.send_text(json.dumps({"type": "riders", "riders": public_list(rider_id)}))
            elif t == "leave":
                await drop_rider(rider_id)
                rider_id = None
                break
            elif t == "msg":
                # Direct message by rider id (any distance)
                to_id = msg.get("to")
                text = (msg.get("text") or "").strip()[:200]
                if to_id and text and r and to_id in riders and to_id != rider_id:
                    await send_to(to_id, {"type": "msg", "from": r["name"], "fromId": rider_id, "text": text})
            elif t == "broadcast":
                # "All" = everyone currently in range
                text = (msg.get("text") or "").strip()[:200]
                if text and r:
                    await send_near(rider_id, {"type": "msg", "from": r["name"] + " (all)",
                                               "fromId": None, "text": text})
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        # A dropped connection is not a leave: keep the rider so nearby riders see
        # 'last seen' and get a stale alert. Explicit 'leave' or the 30 min purge removes them.
        if rider_id:
            r = riders.get(rider_id)
            if r and r.get("ws") is ws:
                r["ws"] = None
                if r["lat"] is None:
                    await drop_rider(rider_id)

# Bundled client assets (same files Capacitor loads from webDir)
app.mount("/leaflet", StaticFiles(directory=WWW_DIR / "leaflet"), name="www_leaflet")
app.mount("/leaflet-rotate", StaticFiles(directory=WWW_DIR / "leaflet-rotate"), name="www_leaflet_rotate")
