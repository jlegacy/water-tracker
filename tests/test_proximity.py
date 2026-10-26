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
    reset(); add("me", 0); add("a24", 24); add("a26", -26); add("a28", -28)  # opposite side of me
    assert sorted(main.update_links("me")) == both("me", "a24", True)
    main.riders["a24"]["lat"] = at(26.5)[0]          # 26.5: still shown (hysteresis)
    assert main.update_links("a24") == []
    assert ("me", "a24") in main.links and ("a24", "me") in main.links
    main.riders["a24"]["lat"] = at(27.5)[0]          # past 27: dropped
    assert sorted(main.update_links("a24")) == both("a24", "me", False)
    main.riders["a24"]["lat"] = at(26)[0]            # 26 (outside 25): not re-shown
    assert main.update_links("a24") == []
    main.riders["a24"]["lat"] = at(24.99)[0]
    assert sorted(main.update_links("a24")) == both("a24", "me", True)

def test_valid_range():
    v = main.valid_range
    assert [v(x) for x in (1, 5, 7.3, 27, 49.99, 50)] == [1, 5, 7.3, 27, 49.99, 50]   # any float 1-50
    assert v(0.4) == 1 and v(-5) == 1 and v(100) == 50 and v("12.5") == 12.5        # clamped
    assert v(None) == 5 and v("x") == 5 and v(float("nan")) == 5 and v("inf") == 5
    assert main.new_rider("x", None)["range"] == 5          # old client default
    assert main.new_rider("x", None, rng=50)["range"] == 50

def test_pair_in_range_custom_range():
    p = main.pair_in_range
    assert p(40, False, 40) and not p(40.1, False, 40)
    assert p(41.9, True, 40) and not p(42.1, True, 40)
    assert not p(26, False, 25) and p(26, False, 30)

def test_asymmetric_ranges():
    reset(); add("me", 0); add("r24", 24); add("r32", 32); add("r48", 48); add("r52", -52)
    main.riders["me"]["range"] = 50
    for r in list(main.riders): main.update_links(r)
    assert sorted(e["id"] for e in main.public_list("me")) == ["r24", "r32", "r48"]  # 52 > 50
    # r32 (default 25) does not see me back; r24 does
    assert "me" not in [e["id"] for e in main.public_list("r32")]
    assert "me" in [e["id"] for e in main.public_list("r24")]
    # my broadcasts reach only riders whose range includes me
    assert sorted(main.viewers("me")) == ["r24"]
    assert sorted(main.viewers("r48")) == ["me", "r24", "r32"]   # r24/r32 are 24/16 mi from r48
    assert "me" not in main.viewers("r52") and main.viewers("r52") == []
    # shrink live to 30: 48 drops; 32 is kept by hysteresis (<= 30 + 2)
    main.riders["me"]["range"] = 30
    ch = main.update_links("me")
    assert sorted(x for x in ch if x[0] == "me") == [("me", "r48", False)]
    main.riders["me"]["range"] = 25                   # 32 > 27: drops
    assert sorted(x for x in main.update_links("me") if x[0] == "me") == [("me", "r32", False)]
    main.riders["me"]["range"] = 35
    ch = main.update_links("me")
    assert ("me", "r32", True) in ch and ("me", "r48", True) not in ch

def test_no_fix_sees_nobody():
    reset(); add("me", 0); add("nofix")
    assert main.update_links("nofix") == []
    assert main.update_links("me") == []
    assert main.public_list("nofix") == [] and main.public_list("me") == []

def test_public_list_is_per_viewer():
    reset(); add("me", 0); add("near", 10); add("far", 40); add("far2", 45)
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

def test_effective_range_sos_uses_max():
    assert main.MAX_RANGE_MI == 50 and main.MIN_RANGE_MI == 1
    reset(); add("rx", 0)["range"] = 5; add("norm", 30); s = add("sos", -30)
    for r in list(main.riders): main.update_links(r)
    assert main.seen_by("rx") == []
    s["sos"] = True; main.update_links("sos")
    assert main.seen_by("rx") == ["sos"] and "rx" in main.viewers("sos")
    s["sos"] = False; ch = main.update_links("sos")
    assert ("rx", "sos", False) in ch and main.seen_by("rx") == []
