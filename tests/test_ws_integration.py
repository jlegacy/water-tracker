"""Integration: real WebSocket clients against a local uvicorn server."""
import asyncio, json, math, os, pathlib, socket, subprocess, sys, time
import pytest, websockets

ROOT = pathlib.Path(__file__).resolve().parents[1]
MI = 3958.8 * math.pi / 180
BASE = (35.0, -77.0)
def at(mi, lon=BASE[1]): return BASE[0] + mi / MI, lon
_area = iter(range(100))
def area():
    """Each test rides in its own area ~110+ mi from the others (isolation)."""
    return BASE[1] + 2.5 * next(_area)

@pytest.fixture(scope="module")
def url():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    env = dict(os.environ, STALE_SECS="3", STALE_CHECK_SECS="1")
    p = subprocess.Popen([sys.executable, "-m", "uvicorn", "main:app", "--port", str(port)], cwd=ROOT, env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(100):
        try: socket.create_connection(("127.0.0.1", port), 0.2).close(); break
        except OSError: time.sleep(0.1)
    yield f"ws://127.0.0.1:{port}/ws"
    p.terminate(); p.wait()

class C:
    def __init__(s, url, rid, lon=None): s.url, s.id, s.msgs, s.lon = url, rid, [], lon if lon is not None else LON[0]
    async def open(s, mi=None, **kw):
        # Server ignores range (fixed 50 mi); 25 is sent like an old client would; range=None omits it
        kw.setdefault("range", 25)
        if kw["range"] is None: kw.pop("range")
        s.ws = await websockets.connect(s.url)
        await s.ws.send(json.dumps(dict(type="join", id=s.id, name=s.id, **kw)))
        s.task = asyncio.create_task(s._rx())
        await asyncio.sleep(0.1)
        if mi is not None: await s.move(mi)
        return s
    async def _rx(s):
        try:
            async for m in s.ws: s.msgs.append(json.loads(m))
        except Exception: pass
    async def move(s, mi):
        lat, lon = at(mi, s.lon); await s.send(type="pos", lat=lat, lon=lon, ts=time.time() * 1000); await asyncio.sleep(0.15)
    async def send(s, **m): await s.ws.send(json.dumps(m)); await asyncio.sleep(0.05)
    def of(s, t, **f): return [m for m in s.msgs if m["type"] == t and all(m.get(k) == v for k, v in f.items())]
    def clear(s): s.msgs.clear()
    async def snapshot(s):
        s.clear(); await s.send(type="sync"); await asyncio.sleep(0.15)
        return sorted(r["id"] for r in s.of("riders")[-1]["riders"])
    async def close(s, leave=True):
        if leave: await s.send(type="leave")
        await s.ws.close()

LON = [BASE[1]]
def run(coro):
    LON[0] = area()
    return asyncio.run(coro)

def test_50_mile_list_and_hysteresis(url):
    async def go():
        me = await C(url, "h_me").open(0)
        a, b, c = [await C(url, n).open(mi) for n, mi in (("h49", 49), ("h51", -51), ("h53", -53))]
        assert (await me.snapshot()) == ["h49"]                  # 51/53 hidden
        assert (await b.snapshot()) == ["h53"]
        me.clear(); await a.move(51.5)                           # hysteresis: stays
        assert not me.of("leave", id="h49") and (await me.snapshot()) == ["h49"]
        me.clear(); await a.move(52.5)                           # past 52: explicit leave
        assert me.of("leave", id="h49") and (await me.snapshot()) == []
        me.clear(); await a.move(51)                             # was hidden -> stays hidden
        assert (await me.snapshot()) == []
        me.clear(); await a.move(49)
        assert me.of("pos", id="h49") and (await me.snapshot()) == ["h49"]
        for x in (me, a, b, c): await x.close()
    run(go())

def test_sos_and_alerts_reach_only_nearby(url):
    async def go():
        sos = await C(url, "s_sos").open(0)
        near, far = await C(url, "s_near").open(20), await C(url, "s_far").open(-60)
        await sos.send(type="sos", on=True); await asyncio.sleep(0.1)
        assert near.of("sos", id="s_sos", on=True) and not far.of("sos")   # 60 mi: beyond max range
        # SOS flag carried in snapshot / pos for riders arriving later
        late = await C(url, "s_late").open(5)
        assert any(m.get("id") == "s_sos" and m.get("sos") for m in late.of("pos"))
        # far rider drives into range -> sees SOS rider with sos flag
        far.clear(); await far.move(-45)   # 45 mi: inside max range
        assert any(m.get("id") == "s_sos" and m.get("sos") for m in far.of("pos"))  # SOS reaches up to 50 mi
        await sos.send(type="sos", on=False)
        for x in (near, far, late): await x.close()
        await sos.close()
    run(go())

def test_stale_alert_to_nearby_only(url):
    async def go():
        q = await C(url, "q_quiet").open(0)
        near, far = await C(url, "q_near").open(40), await C(url, "q_far").open(-60)
        await q.ws.close()                                        # drop without leave
        for _ in range(60):
            if near.of("alert", id="q_quiet"): break
            await near.send(type="ping"); await far.send(type="ping"); await asyncio.sleep(0.2)
        assert near.of("alert", id="q_quiet") and not far.of("alert")
        for x in (near, far): await x.close()
    run(go())

def test_multiple_leaders(url):
    async def go():
        l1 = await C(url, "l_one").open(0, leader=True)
        l2 = await C(url, "l_two").open(5, leader=True)
        r = await C(url, "l_rider").open(2)
        far = await C(url, "l_far").open(60)
        snap = {e["id"]: e["leader"] for e in (r.clear() or (await r.send(type="sync")) or (await asyncio.sleep(0.15)) or r.of("riders")[-1]["riders"])}
        assert snap == {"l_one": True, "l_two": True}
        r.clear(); far.clear(); await l2.send(type="leader", on=False); await asyncio.sleep(0.1)
        assert r.of("leader", id="l_two", on=False) and l1.of("leader", id="l_two") and not far.of("leader")
        for x in (l1, l2, r, far): await x.close()
    run(go())

def test_messages(url):
    async def go():
        a, b, far = await C(url, "m_a").open(0), await C(url, "m_b").open(10), await C(url, "m_far").open(100)
        await a.send(type="broadcast", text="hi all"); await asyncio.sleep(0.1)
        assert b.of("msg", text="hi all") and not far.of("msg") and not a.of("msg")
        await a.send(type="msg", to="m_far", text="direct"); await asyncio.sleep(0.1)  # direct: by id, any distance
        assert far.of("msg", text="direct", fromId="m_a") and not b.of("msg", text="direct")
        for x in (a, b, far): await x.close()
    run(go())

def test_join_flow_no_fix_and_compat(url):
    async def go():
        nf = await C(url, "j_nofix").open()                     # name only, no fix yet
        assert nf.of("joined", id="j_nofix") and "code" not in nf.of("joined")[0]
        old = await C(url, "j_old").open(1, code="Wake Me Up")  # old client with group: accepted, ignored
        assert old.of("joined") and not old.of("error")
        assert (await nf.snapshot()) == [] and (await old.snapshot()) == []  # no fix: invisible both ways
        await nf.move(0)
        assert (await nf.snapshot()) == ["j_old"] and (await old.snapshot()) == ["j_nofix"]
        old.clear(); await nf.close()
        await asyncio.sleep(0.1); assert old.of("leave", id="j_nofix")
        await old.close()
    run(go())

def test_leave_beacon_by_id(url):
    import urllib.request
    async def go():
        a, b = await C(url, "b_a").open(0), await C(url, "b_b").open(1)
        http = url.replace("ws://", "http://").replace("/ws", "")
        body = json.dumps({"id": "b_a"}).encode()
        r = json.loads(urllib.request.urlopen(urllib.request.Request(http + "/api/leave", data=body, method="POST")).read())
        await asyncio.sleep(0.1)
        assert r["ok"] and b.of("leave", id="b_a")
        try: urllib.request.urlopen(http + "/api/groups"); gone = False
        except Exception: gone = True
        assert gone
        await a.close(); await b.close()
    run(go())

# ---- Per-rider viewing range ----
def test_client_range_ignored(url):
    async def go():
        cs = [await C(url, f"g{i}").open(0.1 * i, range=v) for i, v in enumerate((None, 1, 25, "x", 77))]
        assert all(c.of("joined")[0]["range"] == 50 for c in cs)
        r = {mi: await C(url, f"g{mi}mi").open(mi if mi != 53 else -53) for mi in (24, 48, 53)}
        far = lambda s: sorted(x for x in s if x.endswith("mi"))
        for c in cs: assert far(await c.snapshot()) == ["g24mi", "g48mi"]
        for x in (*cs, *r.values()): await x.close()
    run(go())

def test_range_message_is_noop(url):
    async def go():
        me = await C(url, "w_me").open(0)
        r32, r48 = await C(url, "w32").open(32), await C(url, "w48").open(48)
        assert (await me.snapshot()) == ["w32", "w48"]
        for v in (1, 30, 0.4, 77):
            me.clear(); await me.send(type="range", range=v); await asyncio.sleep(0.15)
            assert me.of("range", range=50) and not me.of("leave") and (await me.snapshot()) == ["w32", "w48"]
        for x in (me, r32, r48): await x.close()
    run(go())

def test_sos_leader_within_50(url):
    async def go():
        sos = await C(url, "k_sos").open(0, leader=True)
        d29 = await C(url, "k29").open(29, range=1)
        d51 = await C(url, "k51").open(-51)
        await sos.send(type="sos", on=True); await asyncio.sleep(0.15)
        assert d29.of("sos", id="k_sos", on=True) and not d51.of("sos")
        await sos.send(type="broadcast", text="all-r"); await asyncio.sleep(0.15)
        assert d29.of("msg", text="all-r") and not d51.of("msg")
        assert "k29" in await sos.snapshot()                                 # symmetric now
        d29.clear(); await sos.send(type="sos", on=False); await asyncio.sleep(0.15)
        assert d29.of("sos", id="k_sos", on=False) and not d29.of("leave", id="k_sos")  # still within 50
        for x in (d29, d51): await x.close()
        await sos.close()
    run(go())

def test_stale_alert_within_50(url):
    async def go():
        q = await C(url, "z_quiet").open(0)
        a, b = await C(url, "z_a").open(45, range=1), await C(url, "z_b").open(-55)
        await q.ws.close()
        for _ in range(60):
            if a.of("alert", id="z_quiet"): break
            await a.send(type="ping"); await b.send(type="ping"); await asyncio.sleep(0.2)
        assert a.of("alert", id="z_quiet") and not b.of("alert")
        for x in (a, b): await x.close()
    run(go())

def test_style_propagates_and_validates(url):
    async def go():
        a = await C(url, "st_a").open(0, color="orange", icon="shark")
        b = await C(url, "st_b").open(3)                        # old client: no style -> defaults
        b.clear(); await b.send(type="sync"); await asyncio.sleep(0.15)
        ra = [r for r in b.of("riders")[-1]["riders"] if r["id"] == "st_a"][0]
        assert (ra["color"], ra["icon"]) == ("orange", "initial")   # icons removed -> default
        a.clear(); await a.send(type="sync"); await asyncio.sleep(0.15)
        rb = [r for r in a.of("riders")[-1]["riders"] if r["id"] == "st_b"][0]
        assert (rb["color"], rb["icon"]) == ("default", "initial")
        b.clear(); await a.send(type="style", color="green", icon="anchor"); await asyncio.sleep(0.1)
        assert b.of("style", id="st_a", color="green", icon="initial")
        b.clear(); await a.send(type="style", color="#ff0000", icon="<script>"); await asyncio.sleep(0.1)
        assert b.of("style", id="st_a", color="default", icon="initial")   # not in allowlist -> defaults
        await a.send(type="style", color="teal", icon="wave"); b.clear(); await a.move(1)
        p = b.of("pos", id="st_a")[-1]; assert (p["color"], p["icon"]) == ("teal", "initial")   # carried on pos
        far = await C(url, "st_far").open(-60); await a.send(type="style", color="lime", icon="fish"); await asyncio.sleep(0.1)
        assert not far.of("style")                               # out of range: not sent
        for x in (a, b, far): await x.close()
    run(go())

def test_sos_within_50_then_hides_past_52(url):
    async def go():
        rx = await C(url, "m_rx").open(0, range=5)
        sos = await C(url, "m_sos").open(-30, range=5)
        assert (await rx.snapshot()) == ["m_sos"]                            # 30 mi visible without SOS
        rx.clear(); await sos.send(type="sos", on=True); await asyncio.sleep(0.15)
        assert rx.of("sos", id="m_sos", on=True)
        rx.clear(); await sos.move(-53); assert rx.of("leave", id="m_sos")   # past 50 + 2
        rx.clear(); await sos.send(type="sos", on=False); await asyncio.sleep(0.15)
        await sos.move(-30); assert (await rx.snapshot()) == ["m_sos"]
        for x in (rx, sos): await x.close()
    run(go())

def test_sos_rider_quiet_alert_reaches_max_range(url):
    async def go():
        rx = await C(url, "q_rx").open(0, range=5)
        sos = await C(url, "q_sos").open(40)
        await sos.send(type="sos", on=True); await asyncio.sleep(0.15)
        await sos.ws.close()
        for _ in range(60):
            if rx.of("alert", id="q_sos"): break
            await rx.send(type="ping"); await asyncio.sleep(0.2)
        assert rx.of("alert", id="q_sos")
        await rx.close()
    run(go())
