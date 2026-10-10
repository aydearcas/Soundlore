"""Control cases for temperature: pairs that should come out hot or cold (profile affinity only)."""
import json, os, math
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = {g["key"]: g for g in json.load(open(os.path.join(ROOT, "build", "genres.json"), encoding="utf-8"))}
idf = json.load(open(os.path.join(ROOT, "build", "idf.json")))
W = {"characteristic": 3, "frequent": 2, "occasional": 1}

def vec(n):
    p = G[n]["profile"]; return {c: W[k] * idf[c] for k in W for c in p[k]}
def cos(a, b):
    va, vb = vec(a), vec(b)
    num = sum(va[c] * vb[c] for c in set(va) & set(vb))
    return num / (math.sqrt(sum(x * x for x in va.values())) * math.sqrt(sum(x * x for x in vb.values())))

HOT = [("thrash metal", "speed metal"), ("deep house", "tech house"), ("drum and bass", "jungle"), ("dubstep", "brostep"),
       ("bebop", "hard bop"), ("punk rock", "pop punk"), ("synthwave", "outrun"), ("death metal", "brutal death metal"),
       ("trance", "progressive trance"), ("shoegaze", "dream pop"), ("hardstyle", "rawstyle"), ("grunge", "alternative rock"),
       ("doom metal", "sludge metal"), ("techno", "minimal techno"), ("metalcore", "deathcore"), ("trap", "drill")]
COLD = [("black metal", "bossa nova"), ("ambient", "grindcore"), ("k-pop", "gregorian chant"), ("dubstep", "bluegrass"),
        ("smooth jazz", "powerviolence"), ("lo-fi hip hop", "speedcore"), ("country", "techno"), ("opera", "drill")]
ok = True
for label, pairs, cond in (("HOT (expected ≥ 0.35)", HOT, lambda s: s >= 0.35), ("COLD (expected ≤ 0.10)", COLD, lambda s: s <= 0.10)):
    print(label)
    for a, b in pairs:
        s = cos(a, b); good = cond(s); ok &= good
        print(f"  {s:.2f}  {'ok' if good else 'CHECK':6} {a} ↔ {b}")
print("ALL OK" if ok else "Some cases need review")
