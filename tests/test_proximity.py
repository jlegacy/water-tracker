"""Unit tests: distance math, range (default 5 mi; scenarios use 25) + hysteresis, per-viewer filtering."""
import asyncio, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import main

import math
MI_PER_DEG_LAT = 3958.8 * math.pi / 180
BASE = (35.0, -77.0)

def at(mi):
    return (BASE[0] + mi / MI_PER_DEG_LAT, BASE[1])

def reset():
    main.riders.clear(); main.links.clear()

def add(rid, mi=None):
    r = main.new_rider(rid, None, rng=25)  # scenarios below use 25 mi geometry
    if mi is not None:
        r["lat"], r["lon"] = at(mi)
    main.riders[rid] = r
    return r

def test_miles_known_values():
    assert main._miles(*BASE, *BASE) == 0
    assert abs(main._miles(*BASE, *at(25)) - 25) < 0.01
    # Raleigh -> Williamston NC is about 88 mi
    assert 85 < main._miles(35.7796, -78.6382, 35.8546, -77.0555) < 91
    # longitude shrinks with latitude
    assert main._miles(60, 0, 60, 1) < main._miles(0, 0, 0, 1) * 0.51

def test_pair_in_range_hysteresis():
    p = lambda d, shown: main.pair_in_range(d, shown, 25)
    assert main.pair_in_range(5.0, False) and not main.pair_in_range(5.1, False)  # default 5 mi
    assert main.pair_in_range(6.0, True) and not main.pair_in_range(6.1, True)    # 5 + 1 pad
    assert p(24.9, False) and p(25.0, False)
    assert not p(25.1, False) and not p(26.5, False)
    assert p(26.5, True) and p(27.0, True)
    assert not p(27.1, True)

def both(a, b, added):
    return sorted([(a, b, added), (b, a, added)])

def test_links_enter_hold_leave():
    reset(); add("me", 0); add("a49", 49); add("a51", -51); add("a53", -53)  # fixed 50 mi, hide past 52
    assert sorted(main.update_links("me")) == both("me", "a49", True)
    main.riders["a49"]["lat"] = at(51.5)[0]          # 51.5: still shown (hysteresis)
    assert main.update_links("a49") == []
    main.riders["a49"]["lat"] = at(52.5)[0]          # past 52: dropped
    assert sorted(main.update_links("a49")) == both("a49", "me", False)
    main.riders["a49"]["lat"] = at(51)[0]            # 51 (outside 50): not re-shown
    assert main.update_links("a49") == []
    main.riders["a49"]["lat"] = at(49.99)[0]
    assert sorted(main.update_links("a49")) == both("a49", "me", True)

def test_valid_range():
    v = main.valid_range   # client ranges ignored: always 50
    assert all(v(x) == 50 for x in (1, 5, 7.3, 0.4, 100, None, "x", float("nan")))
    assert main.new_rider("x", None)["range"] == 50 and main.new_rider("x", None, rng=5)["range"] == 50

def test_pair_in_range_custom_range():
    p = main.pair_in_range
    assert p(40, False, 40) and not p(40.1, False, 40)
    assert p(41.9, True, 40) and not p(42.1, True, 40)
    assert not p(26, False, 25) and p(26, False, 30)

def test_everyone_within_50_symmetric():
    reset(); add("me", 0); add("r24", 24); add("r48", 48); add("r52", -52)
    for r in ("me", "r24", "r48"): main.riders[r]["range"] = 1   # stale client ranges are ignored
    for r in list(main.riders): main.update_links(r)
    assert sorted(e["id"] for e in main.public_list("me")) == ["r24", "r48"]
    assert "me" in [e["id"] for e in main.public_list("r48")]
    assert sorted(main.viewers("me")) == ["r24", "r48"] and main.viewers("r52") == []

def test_no_fix_sees_nobody():
    reset(); add("me", 0); add("nofix")
    assert main.update_links("nofix") == []
    assert main.update_links("me") == []
    assert main.public_list("nofix") == [] and main.public_list("me") == []

def test_public_list_is_per_viewer():
    reset(); add("me", 0); add("near", 10); add("far", 70); add("far2", 95)
    for r in list(main.riders): main.update_links(r)
    assert [e["id"] for e in main.public_list("me")] == ["near"]
    assert sorted(e["id"] for e in main.public_list("far")) == ["far2"]

def test_drop_rider_clears_links():
    reset(); add("me", 0); add("near", 1); main.update_links("me")
    asyncio.run(main.drop_rider("near"))
    assert "near" not in main.riders and not main.links and main.viewers("me") == [] and main.seen_by("me") == []

def test_no_group_api():
    paths = {getattr(r, "path", None) for r in main.app.routes}
    assert "/api/groups" not in paths and "/api/leave" in paths
    assert not hasattr(main, "GROUP_CODES") and not hasattr(main, "groups")

def test_small_range_proportional_pad():
    p, h = main.pair_in_range, main.hide_pad
    assert [h(r) for r in (1, 5, 10, 15, 25, 50)] == [0.2, 1.0, 2.0, 2.0, 2.0, 2.0]
    assert p(0.9, False, 1) and not p(1.1, False, 1)
    assert p(1.15, True, 1) and not p(1.25, True, 1)   # 1 mi: hide past 1.2, not 3
    assert p(5.9, True, 5) and not p(6.1, True, 5)
    assert p(26.9, True, 25) and not p(27.1, True, 25)

def test_effective_range_always_max():
    assert main.MAX_RANGE_MI == 50
    reset(); add("rx", 0)["range"] = 5; add("norm", 30); s = add("sos", -30)
    for r in list(main.riders): main.update_links(r)
    assert sorted(main.seen_by("rx")) == ["norm", "sos"]   # 30 mi seen without SOS
