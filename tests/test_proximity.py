"""Unit tests: distance math, 25-mile range + hysteresis, per-viewer filtering."""
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
    r = main.new_rider(rid, None)
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
    p = main.pair_in_range
    assert p(24.9, False) and p(25.0, False)
    assert not p(25.1, False) and not p(26.5, False)
    assert p(26.5, True) and p(27.0, True)
    assert not p(27.1, True)

def test_links_enter_hold_leave():
    reset(); add("me", 0); add("a24", 24); add("a26", -26); add("a28", -28)  # opposite side of me
    added, removed = main.update_links("me")
    assert sorted(added) == ["a24"] and removed == []
    # a24 drifts to 26.5 mi: still shown (hysteresis)
    main.riders["a24"]["lat"] = at(26.5)[0]
    assert main.update_links("a24") == ([], [])
    assert frozenset(("me", "a24")) in main.links
    # past 27: dropped
    main.riders["a24"]["lat"] = at(27.5)[0]
    assert main.update_links("a24") == ([], ["me"])
    # back to 26 (outside 25): not re-shown until <= 25
    main.riders["a24"]["lat"] = at(26)[0]
    assert main.update_links("a24") == ([], [])
    main.riders["a24"]["lat"] = at(24.99)[0]
    assert main.update_links("a24") == (["me"], [])

def test_no_fix_sees_nobody():
    reset(); add("me", 0); add("nofix")
    assert main.update_links("nofix") == ([], [])
    assert main.update_links("me") == ([], [])
    assert main.public_list("nofix") == [] and main.public_list("me") == []

def test_public_list_is_per_viewer():
    reset(); add("me", 0); add("near", 10); add("far", 40); add("far2", 45)
    for r in list(main.riders): main.update_links(r)
    assert [e["id"] for e in main.public_list("me")] == ["near"]
    assert sorted(e["id"] for e in main.public_list("far")) == ["far2"]

def test_drop_rider_clears_links():
    reset(); add("me", 0); add("near", 1); main.update_links("me")
    asyncio.run(main.drop_rider("near"))
    assert "near" not in main.riders and not main.links and main.neighbors("me") == []

def test_no_group_api():
    paths = {getattr(r, "path", None) for r in main.app.routes}
    assert "/api/groups" not in paths and "/api/leave" in paths
    assert not hasattr(main, "GROUP_CODES") and not hasattr(main, "groups")
