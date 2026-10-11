"""Instrument layer for the two-layer map (prototype of the future artist layer).

Each Instrumentation concept used by at least one genre profile becomes a point on its own plane,
placed at the weighted center of the genres that use it (characteristic 3, frequent 2, occasional 1)
on the 2D genre map, then spread slightly so points do not overlap. The links keep the weights,
so the viewer can draw instrument → genre lines.

Input:  build/concepts.json, build/genres_by_concept.json, build/genre_map.json
Output: build/instrument_layer.json
  {"branches": [label, ...],
   "genres": [key, ...]                       (same order as genre_map.json points)
   "items": [[uid, label, branch_index, x, y, ax, ay, spread, [[genre_index, weight], ...]], ...]}
  x, y: displayed position; ax, ay: weighted center, stretched to fill the plane; spread: weighted
  mean distance of the item's genres from the unstretched center (how genre-crossing the instrument is).

Weighted centers crowd toward the middle of the genre map (an average of many genres lands near
the middle), so the layer is stretched about its center until its 1st-99th percentile range spans
the plane. The order of the points is kept: what is left of a point stays left of it.
"""
import json, math, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
B = os.path.join(ROOT, "build")
W = {"characteristic": 3, "frequent": 2, "occasional": 1}


def stretch(items, lo=1, hi=99, pad=0.03):
    """Stretch the layer per axis so that its lo-hi percentile range spans pad..1-pad."""
    for k in ("ax", "ay"):
        v = sorted(a[k] for a in items)
        a0, a1 = v[int(len(v) * lo / 100)], v[min(len(v) - 1, int(len(v) * hi / 100))]
        for a in items:
            a[k] = min(1, max(0, pad + (a[k] - a0) / max(1e-9, a1 - a0) * (1 - 2 * pad)))
            a["x" if k == "ax" else "y"] = a[k]


def main():
    C = json.load(open(os.path.join(B, "concepts.json"), encoding="utf-8"))
    gbc = json.load(open(os.path.join(B, "genres_by_concept.json"), encoding="utf-8"))
    gmap = json.load(open(os.path.join(B, "genre_map.json"), encoding="utf-8"))
    pts = gmap["points"]
    gi = {p[0]: i for i, p in enumerate(pts)}
    by = {c["id"]: c for c in C["concepts"]}
    ins = [c for c in C["concepts"] if c["facet"] == "INS"]
    roots = [c for c in ins if not c["broader"]]

    def root(c):
        while c["broader"]:
            c = by[c["broader"][0]]
        return c["id"]
    ridx = {r["id"]: i for i, r in enumerate(roots)}

    items = []
    for c in ins:
        u = gbc.get(c["id"]) or {}
        links = {}
        for lvl, w in W.items():
            for g in u.get(lvl, []):
                if g in gi:
                    links[gi[g]] = max(links.get(gi[g], 0), w)
        if not links:
            continue
        tw = sum(links.values())
        ax = sum(pts[i][1] * w for i, w in links.items()) / tw
        ay = sum(pts[i][2] * w for i, w in links.items()) / tw
        spread = sum(math.hypot(pts[i][1] - ax, pts[i][2] - ay) * w for i, w in links.items()) / tw
        items.append(dict(c=c, ax=ax, ay=ay, x=ax, y=ay, spread=spread, links=links, b=ridx[root(c)]))

    stretch(items)
    # spread overlapping points a little, with a spring back to the (stretched) weighted center
    dmin = 0.022
    for _ in range(160):
        for a in items:
            fx = (a["ax"] - a["x"]) * 0.08
            fy = (a["ay"] - a["y"]) * 0.08
            for b in items:
                if a is b:
                    continue
                dx, dy = a["x"] - b["x"], a["y"] - b["y"]
                d = math.hypot(dx, dy)
                if d < dmin:
                    if d < 1e-6:
                        dx, dy, d = (hash(a["c"]["id"]) % 7 - 3) * 1e-3, (hash(b["c"]["id"]) % 5 - 2) * 1e-3, 1e-3
                    f = (dmin - d) / d * 0.5
                    fx += dx * f
                    fy += dy * f
            a["x"] = min(1, max(0, a["x"] + fx))
            a["y"] = min(1, max(0, a["y"] + fy))

    r4 = lambda v: round(v, 4)
    out = dict(branches=[r["label"] for r in roots], genres=[p[0] for p in pts],
               items=[[a["c"]["uid"], a["c"]["label"], a["b"], r4(a["x"]), r4(a["y"]), r4(a["ax"]), r4(a["ay"]), r4(a["spread"]),
                       sorted([[i, w] for i, w in a["links"].items()], key=lambda t: -t[1])] for a in items])
    json.dump(out, open(os.path.join(B, "instrument_layer.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    n = sum(len(a["links"]) for a in items)
    print(f"instrument layer: {len(items)} instruments, {n} links, {len(roots)} branches -> build/instrument_layer.json")


if __name__ == "__main__":
    main()
