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

groups = {}

# Allowed group names. Each is its own isolated group; matching is case-insensitive.
GROUP_CODES = ["Wake Me Up", "Spray & Pray", "Throttle Bottoms", "Salty Seadogs", "Wet Willies", "Full Send Fleet", "Buoy Band", "Rooster Tail Rebels"]
GROUP_BY_UPPER = {c.upper(): c for c in GROUP_CODES}

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

def active_count(code):
    """Riders the list would show as present (have a fix) and not stale."""
    now = time.time()
    n = 0
    for r in groups.get(code, {}).values():
        if r.get("lat") is None:
            continue
        age = now - r["updated"]
        if r.get("stale") or age > STALE_SECS:
            continue
        n += 1
    return n

@app.get("/api/groups")
async def api_groups():
    # Active = has a position and not stale (same bar as the rider list).
    return {"groups": [{"code": c, "active": active_count(c)} for c in GROUP_CODES]}

@app.post("/api/leave")
async def api_leave(request: Request):
    # sendBeacon backup for a closing tab: remove only this rider id in this group
    try:
        data = json.loads(await request.body() or b"{}")
    except Exception:
        return {"ok": False}
    if not isinstance(data, dict):
        return {"ok": False}
    code = GROUP_BY_UPPER.get(" ".join(str(data.get("group") or "").split()).upper())
    rid = str(data.get("id") or "")
    g = groups.get(code) if code else None
    if not g or rid not in g:
        return {"ok": False}
    g.pop(rid, None)
    await broadcast(code, {"type": "leave", "id": rid})
    if not g:
        groups.pop(code, None)
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
            prev.update({"name": name, "ws": ws, "leader": bool(msg.get("leader")),
                         "sos": bool(msg.get("sos"))})
        else:
            groups[code][rider_id] = {"name": name, "lat": None, "lon": None, "ts": None,
                                      "updated": time.time(), "ws": ws, "stale": False,
                                      "leader": bool(msg.get("leader")),
                                      "sos": bool(msg.get("sos"))}
        await ws.send_text(json.dumps({"type": "joined", "id": rider_id, "code": code}))
        await broadcast(code, {"type": "riders", "riders": public_list(code)})

        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            t = msg.get("type")
            if t != "leave" and rider_id and rider_id not in groups.get(code, {}):
                # Removed by a /api/leave beacon while this socket is still alive
                # (e.g. same rider open in another tab): put the rider back.
                groups.setdefault(code, {})[rider_id] = {"name": name, "lat": None, "lon": None,
                    "ts": None, "updated": time.time(), "ws": ws, "stale": False, "leader": False,
                    "sos": False}
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
                        out = {"type": "pos", "id": rider_id,
                               "name": r["name"], "lat": r["lat"], "lon": r["lon"],
                               "ts": r.get("ts"), "leader": bool(r.get("leader")),
                               "sos": bool(r.get("sos"))}
                        # Best-effort thinned trail share (from this pos message only)
                        trail = sanitize_trail(msg.get("trail") if t == "pos" else None)
                        if trail and len(trail) >= 2:
                            out["trail"] = trail
                        await broadcast(code, out)
            elif t == "trail":
                # Explicit trail update / clear from a rider
                pts = sanitize_trail(msg.get("points") if msg.get("points") is not None else msg.get("trail"))
                await broadcast(code, {"type": "trail", "id": rider_id,
                                       "points": pts or []})
            elif t == "leader":
                if rider_id in g:
                    g[rider_id]["leader"] = bool(msg.get("on"))
                    await broadcast(code, {"type": "leader", "id": rider_id,
                                           "on": g[rider_id]["leader"]})
            elif t == "sos":
                if rider_id in g:
                    g[rider_id]["sos"] = bool(msg.get("on"))
                    await broadcast(code, {"type": "sos", "id": rider_id,
                                           "on": g[rider_id]["sos"]})
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
                    "stale": bool(r.get("stale")), "leader": bool(r.get("leader")),
                    "sos": bool(r.get("sos"))})
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

# Bundled client assets (same files Capacitor loads from webDir)
app.mount("/leaflet", StaticFiles(directory=WWW_DIR / "leaflet"), name="www_leaflet")
app.mount("/leaflet-rotate", StaticFiles(directory=WWW_DIR / "leaflet-rotate"), name="www_leaflet_rotate")
