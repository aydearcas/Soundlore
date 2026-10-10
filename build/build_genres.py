"""Build the genre thesaurus, the concept→genres index and the temperature between genres.

Input:  sources/musicbrainz_genres.json, genres/core.txt, genres/profiles_*.txt, build/concepts.json
Output: build/genres.json, build/temperature.json, build/temperature_viewer.json,
        build/genres_by_concept.json, build/idf.json
"""
import json, os, sys, math, heapq
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "build"))
from profiles import resolve, NONMUSICAL

ALPHA = 0.7            # weight of profile affinity vs. tree proximity
GRAPH_ONLY = 0.85      # discount when only tree proximity is available
TOP_N = 25             # neighbors stored per genre
EDGE = {"subgenre": 1.0, "fusion": 1.0, "influence": 1.5}
MAX_DIST = 4.5
LEVEL = {3: "characteristic", 2: "frequent", 1: "occasional"}

def level(t):
    return ("scorching" if t >= 80 else "hot" if t >= 60 else "warm" if t >= 40
            else "cool" if t >= 20 else "cold")

def main():
    mb = json.load(open(os.path.join(ROOT, "sources", "musicbrainz_genres.json"), encoding="utf-8"))
    C = json.load(open(os.path.join(ROOT, "build", "concepts.json"), encoding="utf-8"))
    cid = {c["id"] for c in C["concepts"]}
    core = [x.strip() for x in open(os.path.join(ROOT, "genres", "core.txt"), encoding="utf-8").read().split(";") if x.strip()]
    profiles, errors = resolve(cid)
    if errors:
        print("\n".join(errors)); sys.exit(1)

    # --- MusicBrainz genres
    G = {}
    for g in mb["list"]:
        key = g["name"] + (f" ({g['disambiguation']})" if g["disambiguation"] else "")
        G[g["id"]] = {"mbid": g["id"], "name": g["name"], "disambiguation": g["disambiguation"] or None, "key": key}
    by_key = {v["key"]: k for k, v in G.items()}
    by_name = defaultdict(list)
    for k, v in G.items():
        by_name[v["name"]].append(k)
    def find(n):
        if n in by_key: return by_key[n]
        if len(by_name.get(n, [])) == 1: return by_name[n][0]
        return None

    rel_keys = {"subgenre of": "broader", "subgenres": "narrower", "fusion of": "fusion_of",
                "has fusion genres": "fusion_genres", "influenced by": "influenced_by", "influenced genres": "influenced"}
    for k, g in G.items():
        d = mb["data"].get(k)
        for rk in rel_keys.values():
            g[rk] = []
        g["wikidata"] = None; g["area"] = []; g["links"] = []
        g["relations_complete"] = d is not None
        if d is None:
            continue
        for mk, ok in rel_keys.items():
            g[ok] = [x for x in d.get(mk, []) if x in G]
        wd = d.get("Wikidata", [])
        g["wikidata"] = wd[0] if wd else None
        g["area"] = [x[5:] for x in d.get("from", []) if x.startswith("area:")]
        for lk in ("other databases", "Discogs", "Allmusic", "Bandcamp"):
            g["links"] += [x for x in d.get(lk, []) if x.startswith("http")]
    # make relations symmetric
    for k, g in G.items():
        for a, b in (("broader", "narrower"), ("narrower", "broader"), ("influenced_by", "influenced"), ("fusion_of", "fusion_genres")):
            for o in g[a]:
                if k not in G[o][b]: G[o][b].append(k)

    # --- core set and profiles
    for n in core:
        k = find(n)
        if k: G[k]["core"] = True
    prof = {}
    for n, p in profiles.items():
        k = find(n)
        if k: prof[k] = p
    for k, g in G.items():
        g.setdefault("core", False)
        g["non_musical"] = g["key"] in NONMUSICAL or g["name"] in NONMUSICAL
        p = prof.get(k, {})
        g["profile"] = {LEVEL[w]: sorted(c for c, ww in p.items() if ww == w) for w in (3, 2, 1)} if p else None
        # confidence: the core set was profiled in more detail; the rest by profile size
        g["confidence"] = None if not p else ("high" if g["core"] else "medium" if len(p) >= 6 else "low")

    # --- profile affinity (cosine with IDF weighting)
    N = len(prof)
    df = defaultdict(int)
    for p in prof.values():
        for c in p: df[c] += 1
    idf = {c: math.log((N + 1) / (n + 1)) + 0.05 for c, n in df.items()}
    vec = {k: {c: w * idf[c] for c, w in p.items()} for k, p in prof.items()}
    norm = {k: math.sqrt(sum(x * x for x in v.values())) for k, v in vec.items()}
    inv = defaultdict(list)
    for k, v in vec.items():
        for c, x in v.items(): inv[c].append((k, x))
    def prof_sims(k):
        acc = defaultdict(float)
        for c, x in vec[k].items():
            for k2, y in inv[c]:
                if k2 != k: acc[k2] += x * y
        return {k2: s / (norm[k] * norm[k2]) for k2, s in acc.items()}

    # --- tree distance (bounded Dijkstra)
    adj = defaultdict(list)
    for k, g in G.items():
        for rel, w in (("broader", EDGE["subgenre"]), ("fusion_of", EDGE["fusion"]), ("influenced_by", EDGE["influence"])):
            for b in g[rel]:
                adj[k].append((b, w)); adj[b].append((k, w))
    def graph_dists(k):
        dist = {k: 0.0}; pq = [(0.0, k)]
        while pq:
            d, u = heapq.heappop(pq)
            if d > dist.get(u, 1e9) or d >= MAX_DIST: continue
            for v, w in adj[u]:
                nd = d + w
                if nd <= MAX_DIST and nd < dist.get(v, 1e9):
                    dist[v] = nd; heapq.heappush(pq, (nd, v))
        dist.pop(k); return dist
    def gsim(d):  # 1 step → 0.75, 2 → 0.5, 3 → 0.25, 4+ → 0
        return max(0.0, 1 - d / 4)

    temp = {}
    for k in G:
        gd = graph_dists(k)
        ps = prof_sims(k) if k in vec else {}
        rows = []
        for k2 in set(gd) | set(ps):
            g_s = gsim(gd[k2]) if k2 in gd else 0.0
            if k in vec and k2 in vec:
                t = 100 * (ALPHA * ps.get(k2, 0.0) + (1 - ALPHA) * g_s); basis = "profile+graph"
            else:
                t = 100 * GRAPH_ONLY * g_s; basis = "graph only"
            if t < 5: continue
            shared = []
            if k in prof and k2 in prof:
                sh = [(prof[k][c] * prof[k2][c] * idf[c], c) for c in set(prof[k]) & set(prof[k2])]
                shared = [c for _, c in sorted(sh, reverse=True)[:6]]
            rows.append({"mbid": k2, "name": G[k2]["key"], "t": round(t, 1), "level": level(t),
                         "basis": basis, "graph_distance": gd.get(k2), "shared": shared})
        rows.sort(key=lambda r: (-r["t"], r["name"]))
        temp[k] = rows[:TOP_N]

    # --- concept → genres index
    gbc = defaultdict(lambda: {"characteristic": [], "frequent": [], "occasional": []})
    for k, p in prof.items():
        for c, w in p.items():
            gbc[c][LEVEL[w]].append(G[k]["key"])
    for c in gbc:
        for lv in gbc[c]: gbc[c][lv].sort()

    B = os.path.join(ROOT, "build")
    json.dump(sorted(G.values(), key=lambda g: g["key"]), open(os.path.join(B, "genres.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump({G[k]["key"]: v for k, v in temp.items()}, open(os.path.join(B, "temperature.json"), "w", encoding="utf-8"), ensure_ascii=False)
    # compact version for the viewer: [name, t, graph_only(0/1), distance, [shared]]
    compact = {G[k]["key"]: [[r["name"], r["t"], int(r["basis"] == "graph only"), r["graph_distance"], r["shared"]] for r in v[:20]] for k, v in temp.items() if v}
    json.dump(compact, open(os.path.join(B, "temperature_viewer.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    json.dump(gbc, open(os.path.join(B, "genres_by_concept.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump({c: round(v, 3) for c, v in idf.items()}, open(os.path.join(B, "idf.json"), "w", encoding="utf-8"))
    conf = defaultdict(int)
    for g in G.values(): conf[g["confidence"]] += 1
    print(f"genres: {len(G)} | with profile: {len(prof)} | non-musical: {sum(g['non_musical'] for g in G.values())} | "
          f"confidence: {dict(conf)} | concepts used: {len(gbc)}/{len(cid)}")

if __name__ == "__main__":
    main()
