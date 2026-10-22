#!/usr/bin/env python3
"""Build data/nc_ramps.json: OpenStreetMap boat ramps (leisure=slipway) and
marinas (leisure=marina) for North Carolina.

Usage:
  pip install osmium
  curl -LO https://download.geofabrik.de/north-america/us/north-carolina-latest.osm.pbf
  python3 scripts/build_ramps.py north-carolina-latest.osm.pbf data/nc_ramps.json

Ways/relations are reduced to the centroid of their nodes. Entries of the
same type within ~50 m are merged (a named entry wins).
Data (c) OpenStreetMap contributors, ODbL.
"""
import datetime, json, math, sys
import osmium

TAGS = {"slipway": "ramp", "marina": "marina"}


class H(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.items = []

    def _add(self, kind, osm_id, tags, lat, lon):
        self.items.append({"type": kind, "name": tags.get("name") or "",
                           "lat": round(lat, 6), "lon": round(lon, 6), "osm_id": osm_id})

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
        # multipolygon relations only (closed ways handled in way())
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
    items = sorted(items, key=lambda x: (x["name"] == "", x["osm_id"]))  # named first
    kept, grid = [], {}
    for it in items:
        cell = (round(it["lat"] * 200), round(it["lon"] * 200))  # ~500 m cells
        near = [k for dy in (-1, 0, 1) for dx in (-1, 0, 1) for k in grid.get((cell[0] + dy, cell[1] + dx), [])]
        if any(k["type"] == it["type"] and meters(k, it) < dist for k in near):
            continue
        kept.append(it)
        grid.setdefault(cell, []).append(it)
    return kept


def main(src, dst):
    h = H()
    h.apply_file(src, locations=True, idx="flex_mem")
    raw = len(h.items)
    items = dedupe(h.items)
    items.sort(key=lambda x: (x["lat"], x["lon"]))
    out = {"source": "OpenStreetMap contributors, ODbL", "generated": datetime.date.today().isoformat(),
           "region": "North Carolina", "items": items}
    with open(dst, "w") as f:
        json.dump(out, f, separators=(",", ":"))
    c = {t: sum(1 for i in items if i["type"] == t) for t in ("ramp", "marina")}
    print(f"raw={raw} kept={len(items)} {c}")


if __name__ == "__main__":
    main(*(sys.argv[1:3] if len(sys.argv) > 2 else ("north-carolina-latest.osm.pbf", "data/nc_ramps.json")))
