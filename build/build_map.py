"""2D genre map: t-SNE layout of the IDF-weighted profile vectors, plus a family for coloring.

Input:  build/genres.json, build/idf.json, build/temperature.json
Output: build/genre_map.json  {"families": [...], "points": [[key, x, y, family_index, core(0/1)], ...]}
"""
import json, os, math
from collections import deque, Counter
import numpy as np
from sklearn.manifold import TSNE

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
B = os.path.join(ROOT, "build")
W = {"characteristic": 3, "frequent": 2, "occasional": 1}

# Families (fixed order = fixed color slots). Each lists the MusicBrainz genres that anchor it.
FAMILIES = [
    ("Rock & punk", ["rock", "punk", "punk rock", "post-punk", "alternative rock", "indie rock", "hardcore punk", "rock and roll", "new wave"]),
    ("Electronic", ["electronic", "edm", "house", "techno", "trance", "drum and bass", "dubstep", "breakbeat", "hardcore techno",
                    "ambient", "downtempo", "synth-pop", "electro", "idm", "industrial", "uk garage", "hardstyle", "synthwave"]),
    ("Folk & country", ["folk", "country", "bluegrass", "celtic", "singer-songwriter", "americana", "polka"]),
    ("Pop", ["pop", "dance-pop", "j-pop", "k-pop", "c-pop", "europop", "schlager", "kayōkyoku", "trot", "indian pop", "brega"]),
    ("Hip hop, R&B & soul", ["hip hop", "r&b", "soul", "funk", "disco", "gospel", "trap", "drill", "contemporary r&b", "spirituals"]),
    ("Jazz & blues", ["jazz", "blues", "swing", "ragtime", "boogie-woogie"]),
    ("Metal", ["metal", "heavy metal", "black metal", "death metal", "doom metal", "thrash metal", "metalcore", "grindcore"]),
    ("Latin, Caribbean & African", ["latin", "salsa", "cumbia", "reggae", "reggaeton", "samba", "bossa nova", "tango", "flamenco",
                    "regional mexicano", "son cubano", "calypso", "soca", "zouk", "highlife", "soukous", "afrobeats (West African urban/pop music)",
                    "afrobeat (funk/soul + West African sounds)", "amapiano", "dancehall", "ska", "forró", "mpb", "merengue", "bachata"]),
]
OTHER = "Classical, traditional & other"

def spread(Y, dmin=0.0065, iters=60):
    """Separate overlapping points so every genre stays clickable.

    Genres with identical profiles land on the same spot: first fan them out on a small
    golden-angle spiral around that spot, then push apart any pair closer than `dmin`
    (grid-accelerated), moving points as little as possible.
    """
    Y = Y.copy()
    groups = {}
    for i, (x, y) in enumerate(Y):
        groups.setdefault((round(x, 4), round(y, 4)), []).append(i)
    golden = math.pi * (3 - math.sqrt(5))
    for idx in groups.values():
        if len(idx) < 2: continue
        cx, cy = Y[idx].mean(0)
        for n, i in enumerate(sorted(idx)):
            r = dmin * 0.75 * math.sqrt(n + 0.5)
            Y[i] = (cx + r * math.cos(n * golden), cy + r * math.sin(n * golden))
    for _ in range(iters):
        grid = {}
        for i, (x, y) in enumerate(Y):
            grid.setdefault((int(x / dmin), int(y / dmin)), []).append(i)
        moved = 0
        for (gx, gy), cell in grid.items():
            near = [j for dx in (-1, 0, 1) for dy in (-1, 0, 1) for j in grid.get((gx + dx, gy + dy), [])]
            for i in cell:
                for j in near:
                    if j <= i: continue
                    d = Y[j] - Y[i]; dist = math.hypot(*d)
                    if dist < dmin:
                        if dist < 1e-9:
                            d = np.array([math.cos(i), math.sin(i)]); dist = 1.0
                        push = (dmin - dist) / 2 * d / dist
                        Y[i] -= push; Y[j] += push; moved += 1
        if not moved: break
    return (Y - Y.min(0)) / (Y.max(0) - Y.min(0))

def main():
    G = json.load(open(os.path.join(B, "genres.json"), encoding="utf-8"))
    idf = json.load(open(os.path.join(B, "idf.json")))
    T = json.load(open(os.path.join(B, "temperature.json"), encoding="utf-8"))
    GM = {g["mbid"]: g for g in G}
    GK = {g["key"]: g for g in G}

    # --- family: nearest anchor going up the tree (subgenre of, then fusion of)
    anchor = {}
    for i, (_, roots) in enumerate(FAMILIES):
        for r in roots:
            if r in GK: anchor.setdefault(GK[r]["mbid"], i)
    def family_up(g):
        seen = {g["mbid"]}; q = deque([g["mbid"]])
        while q:
            u = q.popleft()
            if u in anchor: return anchor[u]
            for v in GM[u]["broader"] + GM[u]["fusion_of"]:
                if v not in seen: seen.add(v); q.append(v)
        return None
    fam = {g["key"]: family_up(g) for g in G}
    metal = next(i for i, f in enumerate(FAMILIES) if f[0] == "Metal")
    for g in G:  # any genre named "... metal" belongs to Metal, whatever its other parents
        if " metal" in f" {g['name']}" and g["name"] != "metal": fam[g["key"]] = metal
    # fallback: majority family among the hottest neighbors with a profile basis
    for _ in range(2):
        for g in G:
            if fam[g["key"]] is None:
                votes = Counter(fam[r["name"]] for r in T.get(g["key"], [])[:10] if fam.get(r["name"]) is not None and r["t"] >= 40)
                if votes: fam[g["key"]] = votes.most_common(1)[0][0]
    other = len(FAMILIES)

    # --- layout from profile vectors
    pts = [g for g in G if g["profile"]]
    concepts = sorted({c for g in pts for lv in W for c in g["profile"][lv]})
    ci = {c: i for i, c in enumerate(concepts)}
    X = np.zeros((len(pts), len(concepts)), dtype=np.float32)
    for r, g in enumerate(pts):
        for lv, w in W.items():
            for c in g["profile"][lv]:
                X[r, ci[c]] = w * idf[c]
    X /= np.linalg.norm(X, axis=1, keepdims=True)
    Y = TSNE(n_components=2, metric="cosine", perplexity=35, init="pca", random_state=7, max_iter=1500).fit_transform(X)
    Y = (Y - Y.min(0)) / (Y.max(0) - Y.min(0))  # normalize to 0..1
    Y = spread(Y)

    points = [[g["key"], round(float(Y[r, 0]), 4), round(float(Y[r, 1]), 4),
               fam[g["key"]] if fam[g["key"]] is not None else other, int(g["core"])] for r, g in enumerate(pts)]
    out = {"families": [f[0] for f in FAMILIES] + [OTHER], "points": points}
    json.dump(out, open(os.path.join(B, "genre_map.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("points:", len(points), "| families:", Counter(out["families"][p[3]] for p in points).most_common())

if __name__ == "__main__":
    main()
