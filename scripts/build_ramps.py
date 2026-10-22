#!/usr/bin/env python3
"""Build data/ramps_us.json: OpenStreetMap boat ramps (leisure=slipway) and
marinas (leisure=marina) for East Coast and Great Lakes states, from Geofabrik extracts.

Usage:
  pip install osmium
  python3 scripts/build_ramps.py data/ramps_us.json NC=north-carolina-latest.osm.pbf SC=south-carolina-latest.osm.pbf ...
  python3 scripts/build_ramps.py data/ramps_us.json --download [ST ...]   # download each state, extract, delete pbf
  Per-state extracts are cached in .ramps_cache/<ST>.json so a rerun only fetches missing states.

Ways/relations are reduced to the centroid of their nodes. Entries of the
same type within ~50 m are merged across all states (a named entry wins).
Output is compact: items are [type(0=ramp,1=marina), name, lat, lon, state].
Data (c) OpenStreetMap contributors, ODbL.
"""
import datetime, json, math, os, subprocess, sys
import osmium

TAGS = {"slipway": "ramp", "marina": "marina"}
STATES = [("ME", "maine"), ("NH", "new-hampshire"), ("MA", "massachusetts"), ("RI", "rhode-island"),
          ("CT", "connecticut"), ("NY", "new-york"), ("NJ", "new-jersey"), ("DE", "delaware"),
          ("MD", "maryland"), ("VA", "virginia"), ("NC", "north-carolina"), ("SC", "south-carolina"),
          ("GA", "georgia"), ("FL", "florida"),
          ("PA", "pennsylvania"), ("OH", "ohio"), ("MI", "michigan"), ("IN", "indiana"), ("IL", "illinois"),
          ("WI", "wisconsin"), ("MN", "minnesota")]


class H(osmium.SimpleHandler):
    def __init__(self, state):
        super().__init__()
        self.state, self.items, self.bbox = state, [], [90, 180, -90, -180]

    def _add(self, kind, osm_id, tags, lat, lon):
        self.items.append({"type": kind, "name": tags.get("name") or "", "lat": round(lat, 5),
                           "lon": round(lon, 5), "osm_id": osm_id, "state": self.state})

    def node(self, n):
        k = TAGS.get(n.tags.get("leisure"))
        if k and n.location.valid():
            self._add(k, f"n{n.id}", n.tags, n.location.lat, n.location.lon)

    def way(self, w):
        k = TAGS.get(w.tags.get("leisure"))
        if not k:
            return
        pts = [(nd.lat, nd.lon) for nd in w.nodes if nd.location.valid()]
        if pts:
            self._add(k, f"w{w.id}", w.tags, sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))

    def area(self, a):
        if a.from_way():
            return
        k = TAGS.get(a.tags.get("leisure"))
        if not k:
            return
        pts = [(n.lat, n.lon) for r in a.outer_rings() for n in r if n.location.valid()]
        if pts:
            self._add(k, f"r{a.orig_id()}", a.tags, sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


def meters(a, b):
    r = math.radians
    h = math.sin(r(b["lat"] - a["lat"]) / 2) ** 2 + math.cos(r(a["lat"])) * math.cos(r(b["lat"])) * math.sin(r(b["lon"] - a["lon"]) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


def dedupe(items, dist=50):
    items = sorted(items, key=lambda x: (x["name"] == "", x["state"], x["osm_id"]))  # named first
    kept, grid, seen = [], {}, set()
    for it in items:
        if it["osm_id"] in seen:  # same OSM object in two overlapping extracts
            continue
        cell = (round(it["lat"] * 200), round(it["lon"] * 200))  # ~500 m cells
        near = [k for dy in (-1, 0, 1) for dx in (-1, 0, 1) for k in grid.get((cell[0] + dy, cell[1] + dx), [])]
        if any(k["type"] == it["type"] and meters(k, it) < dist for k in near):
            continue
        seen.add(it["osm_id"])
        kept.append(it)
        grid.setdefault(cell, []).append(it)
    return kept


def extract(state, pbf):
    h = H(state)
    h.apply_file(pbf, locations=True, idx="flex_mem")
    b = osmium.io.Reader(pbf).header().box()
    bbox = [round(b.bottom_left.lat, 2), round(b.bottom_left.lon, 2), round(b.top_right.lat, 2), round(b.top_right.lon, 2)]
    return h.items, bbox


def main(dst, args):
    if args[:1] == ["--download"]:
        want = set(args[1:])
        jobs = [(s, f"{n}-latest.osm.pbf", True) for s, n in STATES if not want or s in want]
    else:
        jobs = [(a.split("=", 1)[0], a.split("=", 1)[1], False) for a in args]
    allitems, regions = [], {}
    for st, pbf, dl in jobs:
        cache = os.path.join(".ramps_cache", st + ".json")
        if dl and os.path.exists(cache):
            items, bbox = json.load(open(cache))
            regions[st] = bbox
            allitems += items
            print(f"{st}: cached raw={len(items)}", flush=True)
            continue
        if dl:
            subprocess.run(["curl", "-sSfLo", pbf, f"https://download.geofabrik.de/north-america/us/{pbf}"], check=True)
        items, bbox = extract(st, pbf)
        if dl:
            os.remove(pbf)
            os.makedirs(".ramps_cache", exist_ok=True)
            json.dump([items, bbox], open(cache, "w"))
        regions[st] = bbox
        allitems += items
        print(f"{st}: raw={len(items)} bbox={bbox}", flush=True)
    items = dedupe(allitems)
    items.sort(key=lambda x: (x["lat"], x["lon"]))
    out = {"source": "OpenStreetMap contributors, ODbL", "generated": datetime.date.today().isoformat(),
           "region": "US East Coast + Great Lakes", "regions": regions,
           "fields": ["type(0=ramp,1=marina)", "name", "lat", "lon", "state"],
           "items": [[0 if i["type"] == "ramp" else 1, i["name"], i["lat"], i["lon"], i["state"]] for i in items]}
    with open(dst, "w") as f:
        json.dump(out, f, separators=(",", ":"), ensure_ascii=False)
    for st in regions:
        print(st, {t: sum(1 for i in items if i["type"] == t and i["state"] == st) for t in ("ramp", "marina")})
    print(f"raw={len(allitems)} kept={len(items)}", {t: sum(1 for i in items if i["type"] == t) for t in ("ramp", "marina")})


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
