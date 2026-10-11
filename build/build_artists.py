"""Artist layer: MusicBrainz artists described through their community-voted genres.

Artists are not part of the thesaurus. Each artist is linked to Soundlore genres by the MusicBrainz
genre votes, and everything else is derived from those links:
  - its profile is the vote-weighted mix of its genres' profiles (computed in the viewer from genres.json);
  - its position on the genre map is the vote-weighted center of its genres;
  - its similar artists come from the same mix (IDF-weighted resource vectors, like genre temperature)
    blended with direct genre overlap.

Input:  sources/musicbrainz/artist_genres_extract.jsonl.gz (from build/filter_artists.py)
        build/genres.json, build/genre_map.json, build/idf.json
Output: build/artists.json            artist records (one array per artist, see FIELDS)
        build/artist_neighbors.json   similar artists, parallel to artists.json
        build/artists_stats.json      counts for the landing and about pages

Selection (the cut-off was chosen with the counts from filter_artists.py):
  an artist is kept when its best-voted genre has at least MIN_VOTES votes, or (with --wd-total N) when it
  has a Wikidata item and its genre votes add up to at least N; within an artist,
  a genre is kept when it has at least REL of the best genre's votes (drops stray single tags).

License: artist core data is CC0; the artist-genre links come from MusicBrainz genres/tags,
CC BY-NC-SA 3.0. The output files carry that notice.
"""
import argparse, gzip, hashlib, json, math, os
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
B = os.path.join(ROOT, "build")
SRC = os.path.join(ROOT, "sources", "musicbrainz", "artist_genres_extract.jsonl.gz")
LW = {"characteristic": 3, "frequent": 2, "occasional": 1}
FIELDS = ["id", "name", "type", "area", "cc", "begin", "end", "wikidata", "disambiguation", "votes",
          "genres", "x", "y", "family", "spread", "source", "sitelinks"]
# source: 0 = genres from MusicBrainz votes, 1 = genres from Wikidata (P136), each weighted 1
LICENSE = ("Artists: MusicBrainz artist data (CC0); Wikidata sitelinks and genres (CC0) for artists with source 1. "
           "Artist-genre links with source 0: MusicBrainz genre votes, "
           "CC BY-NC-SA 3.0 (https://musicbrainz.org/doc/About/Data_License). Profiles, positions and "
           "similar artists derived by Soundlore from those links, same license.")


def jitter(mbid, scale):
    h = hashlib.md5(mbid.encode()).digest()
    a = h[0] / 255 * 2 * math.pi
    r = scale * (0.25 + 0.75 * math.sqrt(h[1] / 255))
    return r * math.cos(a), r * math.sin(a)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-votes", type=int, default=2, help="votes of the best-voted genre (default 2)")
    ap.add_argument("--wd-total", type=int, default=0,
                    help="also keep artists with a Wikidata item whose genre votes add up to at least this (0: off)")
    ap.add_argument("--wd-sitelinks", type=int, default=3,
                    help="add artists without enough MusicBrainz votes whose Wikidata item has at least this many sitelinks and a music genre (0: off)")
    ap.add_argument("--rel", type=float, default=0.25, help="keep genres with at least this share of the top votes")
    ap.add_argument("--max-genres", type=int, default=8)
    ap.add_argument("--neighbors", type=int, default=12)
    ap.add_argument("--src", default=SRC)
    ap.add_argument("--reuse-neighbors", action="store_true", help="keep build/artist_neighbors.json (same selection); only recompute the rest")
    a = ap.parse_args()

    G = json.load(open(os.path.join(B, "genres.json"), encoding="utf-8"))
    gmap = json.load(open(os.path.join(B, "genre_map.json"), encoding="utf-8"))
    idf = json.load(open(os.path.join(B, "idf.json"), encoding="utf-8"))
    meta_path = a.src.replace(".jsonl.gz", "") + ".meta.json"
    meta = json.load(open(meta_path, encoding="utf-8")) if os.path.exists(meta_path) else {}
    gi = {g["mbid"]: i for i, g in enumerate(G)}
    pos = {p[0]: (p[1], p[2], p[3]) for p in gmap["points"]}
    keys = [g["key"] for g in G]

    # --- Wikidata: sitelinks and genres (P136) of artists with a MusicBrainz ID (build/fetch_wikidata_artists.py)
    WD = os.path.join(ROOT, "sources", "wikidata")
    wd_sl, wd_g = {}, {}
    if a.wd_sitelinks and os.path.exists(os.path.join(WD, "artists_wikidata.tsv.gz")):
        qid2g = {g["wikidata"]: i for i, g in enumerate(G) if g.get("wikidata") and not g["non_musical"]}
        parents = {}
        for line in open(os.path.join(WD, "genre_parents.tsv"), encoding="utf-8").read().splitlines()[1:]:
            q, _, ps = (line.split("\t") + ["", ""])[:3]
            parents[q] = ps.split()
        memo = {}
        def to_genres(q):
            # the Soundlore genre with that Wikidata item, else the nearest ones up the class tree (two steps)
            if q in memo: return memo[q]
            if q in qid2g: memo[q] = [qid2g[q]]; return memo[q]
            level, seen = [q], {q}
            for _ in range(2):
                nxt = [p for x in level for p in parents.get(x, []) if p not in seen]
                seen.update(nxt)
                hit = sorted({qid2g[p] for p in nxt if p in qid2g})
                if hit: memo[q] = hit; return hit
                level = nxt
            memo[q] = []; return []
        with gzip.open(os.path.join(WD, "artists_wikidata.tsv.gz"), "rt", encoding="utf-8") as f:
            next(f)
            for line in f:
                q, mbid, sl, gq = (line.rstrip("\n").split("\t") + [""])[:4]
                sl = int(sl or 0)
                wd_sl[mbid] = max(sl, wd_sl.get(mbid, 0))
                gs = []
                for x in gq.split():
                    for i in to_genres(x):
                        if i not in gs: gs.append(i)
                if gs: wd_g[mbid] = gs
        print(f"Wikidata: {len(wd_sl):,} artists with a MusicBrainz ID, {len(wd_g):,} with a genre that maps to Soundlore")

    # --- read and select
    types, tix = [], {}
    arts = []
    read = 0
    with gzip.open(a.src, "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            read += 1
            gs = [(gi[m], v) for m, v in r["g"] if m in gi and v > 0]
            gs.sort(key=lambda t: -t[1])
            top = gs[0][1] if gs else 0
            total = sum(v for _, v in gs)
            sl = wd_sl.get(r["id"], 0)
            src = "mb"
            if not gs or (top < a.min_votes and not (a.wd_total and r.get("wd") and total >= a.wd_total)):
                # not enough MusicBrainz votes: take the genres from Wikidata when the artist is documented enough
                if not (a.wd_sitelinks and sl >= a.wd_sitelinks and r["id"] in wd_g):
                    continue
                src = "wd"
                gs = [(i, 1) for i in wd_g[r["id"]]][: a.max_genres]
            else:
                cut = max(1, math.ceil(a.rel * top))
                gs = [(i, v) for i, v in gs if v >= cut][: a.max_genres]
            t = r.get("type") or ""
            if t not in tix:
                tix[t] = len(types); types.append(t)
            allv = sorted((v for _, v in r["g"]), reverse=True)
            # list order: votes of the five best genres, each capped at 20, so that a few heavily
            # self-tagged or fan-voted entries do not lead the list; then total votes
            # or, when larger, 1.5 x the Wikidata sitelinks (up to 100): how documented the artist is
            rank = max(sum(min(v, 20) for v in allv[:5]), min(100, 1.5 * sl))
            arts.append(dict(r=r, g=gs, t=tix[t], votes=sum(allv), rank=rank, src=src, sl=sl))
    arts.sort(key=lambda x: (-x["rank"], -x["votes"], x["r"]["name"] or ""))
    n = len(arts)
    nwd = sum(1 for x in arts if x["src"] == "wd")
    print(f"{read:,} artists read, {n:,} kept: {n - nwd:,} from MusicBrainz votes, {nwd:,} with genres from Wikidata (>= {a.wd_sitelinks} sitelinks)")

    # --- position: vote-weighted center of the genres on the map
    for x in arts:
        on = [(pos[keys[i]], v) for i, v in x["g"] if keys[i] in pos and not G[i]["non_musical"]]
        if not on:
            x["xy"] = None; x["c"] = None; continue
        tw = sum(v for _, v in on)
        ax = sum(p[0] * v for p, v in on) / tw
        ay = sum(p[1] * v for p, v in on) / tw
        x["spread"] = sum(math.hypot(p[0] - ax, p[1] - ay) * v for p, v in on) / tw
        x["c"] = (ax, ay)
        x["fam"] = pos[keys[x["g"][0][0]]][2] if keys[x["g"][0][0]] in pos else on[0][0][2]

    # Weighted centers crowd toward the middle of the genre map, so the layer is stretched per axis
    # (order kept); the viewer draws the artist plane larger than the genre plane (1.5x in 3D, 2x in 2D). Artists with the same genres share a
    # center: they are laid out around it on a sunflower spiral (even density, best-documented artists in the
    # middle), so a crowded center becomes a filled disc whose size shows how many artists it holds.
    placed = [x for x in arts if x.get("c")]
    for k in (0, 1):
        v = np.array([x["c"][k] for x in placed])
        a0, a1 = np.percentile(v, 1), np.percentile(v, 99)
        for x in placed:
            # the 1st-99th percentile range fills 0.1-0.9: the outer 10% on each side is room for the
            # outlying artists, which then spread out instead of piling up on the edge
            x.setdefault("s", [0, 0])[k] = min(1, max(0, 0.1 + (x["c"][k] - a0) / max(1e-9, a1 - a0) * 0.8))
    groups = {}
    for x in placed:  # arts are in rank order, so each group starts with its best-documented artist
        groups.setdefault((round(x["s"][0], 3), round(x["s"][1], 3)), []).append(x)
    golden = math.pi * (3 - math.sqrt(5))
    for g in groups.values():
        cx = sum(x["s"][0] for x in g) / len(g); cy = sum(x["s"][1] for x in g) / len(g)
        if len(g) == 1:
            dx, dy = jitter(g[0]["r"]["id"], 0.003)
            g[0]["xy"] = (min(1, max(0, cx + dx)), min(1, max(0, cy + dy))); continue
        for k, x in enumerate(g):
            r = 0.0013 * math.sqrt(k + 0.5)
            x["xy"] = (min(1, max(0, cx + r * math.cos(k * golden))), min(1, max(0, cy + r * math.sin(k * golden))))
    big = sorted((len(g) for g in groups.values()), reverse=True)[:5]
    print(f"map: {len(groups):,} distinct centers; largest groups {big}")

    # --- similar artists: resource mix (IDF-weighted) + genre overlap, cosine
    concepts = sorted(idf)
    ci = {c: j for j, c in enumerate(concepts)}
    PV = np.zeros((len(G), len(concepts)), dtype=np.float32)
    for i, g in enumerate(G):
        if g["profile"] and not g["non_musical"]:
            for lvl, w in LW.items():
                for c in g["profile"][lvl]:
                    if c in ci:
                        PV[i, ci[c]] = w * idf[c]
    AG = np.zeros((n, len(G)), dtype=np.float32)
    for k, x in enumerate(arts):
        tw = sum(v for _, v in x["g"])
        for i, v in x["g"]:
            AG[k, i] = v / tw
    def unit(M):
        nr = np.linalg.norm(M, axis=1, keepdims=True); nr[nr == 0] = 1
        return M / nr
    AC = unit(AG @ PV)
    AGu = unit(AG)
    K = a.neighbors
    # Similar artists. Two thirds of the places (8 of 12) go to the best-documented artists among the
    # close matches (similarity >= max(0.6, best - 0.12)), so that the list shows reference artists and
    # not only obscure ones with identical genres; the remaining places go to the closest matches.
    # Everything is shown with its similarity; the full list of a genre's artists is in the Artists tab.
    rank = np.array([x["rank"] for x in arts], dtype=np.float32)
    POP = np.log1p(rank) / math.log1p(max(1.0, float(rank.max())))
    NREL = round(K * 2 / 3)
    POOL = 120
    nb = []
    if a.reuse_neighbors:
        nb = json.load(open(os.path.join(B, "artist_neighbors.json"), encoding="utf-8"))["neighbors"]
        assert len(nb) == n, "the selection changed: run without --reuse-neighbors"
    step = max(200, min(2000, int(1e8 / max(1, n))))
    for s in (range(0, n, step) if not a.reuse_neighbors else []):
        S = 0.6 * (AC[s:s + step] @ AC.T) + 0.4 * (AGu[s:s + step] @ AGu.T)
        for r in range(S.shape[0]):
            S[r, s + r] = -9
        m = min(POOL, n - 1)
        idx = np.argpartition(-S, m - 1, axis=1)[:, :m]
        for r in range(S.shape[0]):
            cand = [(int(j), float(S[r, j])) for j in idx[r] if S[r, j] > 0.2]
            if not cand:
                nb.append([]); continue
            cand.sort(key=lambda t: -t[1])
            best = cand[0][1]
            close = [c for c in cand if c[1] >= max(0.6, best - 0.12)]
            rel = sorted(close, key=lambda t: (-POP[t[0]], -t[1]))[:NREL]
            chosen = {j for j, _ in rel}
            rest = [c for c in cand if c[0] not in chosen][: K - len(rel)]
            row = sorted(rel + rest, key=lambda t: -(t[1] + 0.1 * POP[t[0]]))
            flat = []
            for j, v in row:
                flat += [j, round(v * 100)]
            nb.append(flat)
        print(f"  neighbors {min(s + step, n):,}/{n:,}", end="\r", flush=True)
    print()

    # --- write
    r4 = lambda v: round(v, 4)
    used = sorted({i for x in arts for i, _ in x["g"]})
    remap = {i: k for k, i in enumerate(used)}
    rows = []
    for x in arts:
        r = x["r"]
        yr = lambda d: d[:4] if d else None  # years only: the site shows no more, and the file stays small
        rows.append([r["id"], r["name"], x["t"], r.get("area"), r.get("cc"), yr(r.get("begin")), yr(r.get("end")),
                     r.get("wd"), r.get("dis"), x["votes"], [[remap[i], v] for i, v in x["g"]],
                     r4(x["xy"][0]) if x["xy"] else None, r4(x["xy"][1]) if x["xy"] else None,
                     x.get("fam"), round(x["spread"], 3) if x["xy"] else None, 1 if x["src"] == "wd" else 0, x["sl"]])
    out = dict(license=LICENSE, dump=meta.get("dump"), min_votes=a.min_votes, wd_total=a.wd_total, fields=FIELDS, types=types,
               genres=[keys[i] for i in used], artists=rows)
    json.dump(out, open(os.path.join(B, "artists.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    json.dump(dict(license=LICENSE, neighbors=nb), open(os.path.join(B, "artist_neighbors.json"), "w", encoding="utf-8"), separators=(",", ":"))
    per_genre = {}
    for x in arts:
        for i, _ in x["g"]:
            per_genre[keys[i]] = per_genre.get(keys[i], 0) + 1
    st = dict(artists=n, read=read, dump=meta.get("dump"), min_votes=a.min_votes, wd_total=a.wd_total, rel=a.rel,
              on_map=sum(1 for x in arts if x["xy"]), links=sum(len(x["g"]) for x in arts),
              genres_with_artists=len(per_genre), from_wikidata=sum(1 for x in arts if x["src"] == "wd"), wd_sitelinks=a.wd_sitelinks, types={t or "unknown": sum(1 for x in arts if x["t"] == i) for i, t in enumerate(types)})
    json.dump(st, open(os.path.join(B, "artists_stats.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    sz = lambda f: os.path.getsize(os.path.join(B, f)) / 1e6
    print(f"artists.json {sz('artists.json'):.1f} MB, artist_neighbors.json {sz('artist_neighbors.json'):.1f} MB; "
          f"{st['on_map']:,} on the map, {st['links']:,} artist-genre links, {st['genres_with_artists']:,} genres with artists")


if __name__ == "__main__":
    main()
