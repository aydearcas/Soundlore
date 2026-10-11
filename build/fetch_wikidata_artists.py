"""Fetch from Wikidata the artists that have a MusicBrainz ID, with their genres and their number of sitelinks.

Used to add socially relevant artists that have few or no MusicBrainz genre votes (many Spanish,
French, Italian, German or Portuguese artists, for example). Wikidata data is CC0.
Runs on a computer with internet access (the Wikidata Query Service), standard library only.

Usage:  python build/fetch_wikidata_artists.py [--min-sitelinks 2]

Output (sources/wikidata/):
  artists_wikidata.tsv.gz   qid, MusicBrainz artist ID, sitelinks, genre QIDs (space separated)
  genre_parents.tsv         every genre QID used: label, then its 'subclass of' / 'instance of' parents
  artist_mbids.txt          MBIDs to keep in a second pass of build/filter_artists.py (--also)
  wikidata_counts.txt       artists by sitelinks threshold, and the sitelinks of a few reference artists

Sitelinks count every Wikimedia page about the item (Wikipedias in all languages, plus Commons,
Wikiquote...), so they are a language-neutral measure of how documented an artist is.
"""
import argparse, gzip, json, os, sys, time, urllib.parse, urllib.request
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "sources", "wikidata")
EP = "https://query.wikidata.org/sparql"
UA = "Soundlore/0.10 (music thesaurus research project; https://github.com/aydearcas/Soundlore) python-urllib"
HEX = "0123456789abcdef"

Q_ARTISTS = """SELECT ?item ?mbid ?sl (GROUP_CONCAT(DISTINCT STRAFTER(STR(?g), "entity/"); separator=" ") AS ?genres) WHERE {
  ?item wdt:P434 ?mbid . FILTER(STRSTARTS(?mbid, "%s"))
  ?item wikibase:sitelinks ?sl . FILTER(?sl >= %d)
  OPTIONAL { ?item wdt:P136 ?g }
} GROUP BY ?item ?mbid ?sl"""

Q_PARENTS = """SELECT ?g ?label (GROUP_CONCAT(DISTINCT STRAFTER(STR(?p), "entity/"); separator=" ") AS ?parents) WHERE {
  VALUES ?g { %s }
  OPTIONAL { ?g rdfs:label ?label . FILTER(LANG(?label) = "en") }
  OPTIONAL { ?g wdt:P279|wdt:P31 ?p }
} GROUP BY ?g ?label"""

# reference artists the user named (2026-10-11), to see how many sitelinks they have
REFS = ["Devin Townsend", "Leprous", "Haken", "Assemblage 23", "Artemas", "Edguy", "Avantasia", "Ayreon",
        "Priest", "Covenant", "VNV Nation", "Rata", "RATA", "Axolotes Mexicanos", "La La Love You",
        "Vetusta Morla", "Extremoduro", "Héroes del Silencio", "Mecano", "Love of Lesbian", "Izal",
        "Stromae", "Indochine", "Rammstein", "Caetano Veloso", "Måneskin", "Rosalía", "Camarón de la Isla",
        "Slowdive", "Metallica"]
Q_REFS = """SELECT ?item ?name ?mbid ?sl ?desc (GROUP_CONCAT(DISTINCT STRAFTER(STR(?g), "entity/"); separator=" ") AS ?genres) WHERE {
  VALUES ?name { %s }
  ?item rdfs:label ?name ; wdt:P434 ?mbid ; wikibase:sitelinks ?sl .
  OPTIONAL { ?item schema:description ?desc . FILTER(LANG(?desc) = "en") }
  OPTIONAL { ?item wdt:P136 ?g }
} GROUP BY ?item ?name ?mbid ?sl ?desc ORDER BY ?name DESC(?sl)"""


def sparql(q, tries=5):
    data = urllib.parse.urlencode({"query": q, "format": "json"}).encode()
    for k in range(tries):
        try:
            req = urllib.request.Request(EP, data=data, headers={"User-Agent": UA, "Accept": "application/sparql-results+json"})
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)["results"]["bindings"]
        except urllib.error.HTTPError as e:
            body = e.read()[:300].decode("utf-8", "replace")
            if e.code in (429, 503):
                wait = int(e.headers.get("Retry-After") or 20 * (k + 1))
                print(f"    busy ({e.code}), waiting {wait} s", flush=True); time.sleep(wait); continue
            if e.code == 500 and "timeout" in body.lower():
                raise TimeoutError(body)
            print(f"    HTTP {e.code}: {body[:120]}", flush=True); time.sleep(10 * (k + 1))
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            if k >= 1:
                raise TimeoutError(str(e))
            print(f"    network error: {e}; retrying", flush=True); time.sleep(10)
    raise RuntimeError("Wikidata Query Service did not answer")


def val(b, k):
    return b[k]["value"] if k in b else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-sitelinks", type=int, default=2)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()

    # --- reference artists first (quick, and shows that the service answers)
    names = " ".join(f'"{n}"@{l}' for n in REFS for l in ("en", "es", "mul"))
    refs = sparql(Q_REFS % names)

    # --- all artists with a MusicBrainz ID, by MBID prefix (split further when a query times out)
    rows = {}
    todo = list(HEX)
    while todo:
        p = todo.pop(0)
        try:
            res = sparql(Q_ARTISTS % (p, a.min_sitelinks))
        except TimeoutError:
            print(f"  prefix {p}: timed out, splitting", flush=True)
            todo = [p + h for h in HEX] + todo
            continue
        for b in res:
            qid = val(b, "item").rsplit("/", 1)[-1]
            rows[(qid, val(b, "mbid"))] = (int(val(b, "sl") or 0), val(b, "genres"))
        print(f"  prefix {p:<3} {len(res):>7,} rows   total {len(rows):>8,}   {time.time() - t0:,.0f} s", flush=True)
        time.sleep(1)

    with gzip.open(os.path.join(OUT, "artists_wikidata.tsv.gz"), "wt", encoding="utf-8") as f:
        f.write("qid\tmbid\tsitelinks\tgenres\n")
        for (qid, mbid), (sl, g) in sorted(rows.items(), key=lambda kv: -kv[1][0]):
            f.write(f"{qid}\t{mbid}\t{sl}\t{g}\n")
    with open(os.path.join(OUT, "artist_mbids.txt"), "w", encoding="utf-8") as f:
        for (qid, mbid), (sl, g) in rows.items():
            if g:
                f.write(mbid + "\n")

    # --- genre QIDs: labels and parents, two levels up, to map them to Soundlore genres
    seen, level = {}, sorted({q for _, g in rows.values() for q in g.split()} | {q for b in refs for q in val(b, "genres").split()})
    for depth in range(3):
        nxt = set()
        for i in range(0, len(level), 250):
            chunk = level[i:i + 250]
            for b in sparql(Q_PARENTS % " ".join("wd:" + q for q in chunk)):
                q = val(b, "g").rsplit("/", 1)[-1]
                ps = val(b, "parents").split()
                seen[q] = (val(b, "label"), ps)
                nxt.update(x for x in ps if x not in seen)
            time.sleep(1)
        print(f"  genre parents, level {depth + 1}: {len(seen):,} items", flush=True)
        level = sorted(nxt - set(seen))
        if not level:
            break
    with open(os.path.join(OUT, "genre_parents.tsv"), "w", encoding="utf-8") as f:
        f.write("qid\tlabel\tparents\n")
        for q, (lab, ps) in sorted(seen.items()):
            f.write(f"{q}\t{lab}\t{' '.join(ps)}\n")

    # --- counts
    sg = {}
    try:
        G = json.load(open(os.path.join(ROOT, "build", "genres.json"), encoding="utf-8"))
        sg = {g["wikidata"]: g["key"] for g in G if g.get("wikidata")}
    except OSError:
        pass
    def mapped(q, d=0):
        if q in sg:
            return True
        if d >= 3 or q not in seen:
            return False
        return any(mapped(p, d + 1) for p in seen[q][1])
    sel = set()
    try:
        A = json.load(open(os.path.join(ROOT, "build", "artists.json"), encoding="utf-8"))
        sel = {r[0] for r in A["artists"]}
    except OSError:
        pass
    by_sl = Counter(); by_sl_g = Counter(); by_sl_new = Counter()
    for (qid, mbid), (sl, g) in rows.items():
        b = min(sl, 100)
        by_sl[b] += 1
        if g and any(mapped(q) for q in g.split()):
            by_sl_g[b] += 1
            if mbid not in sel:
                by_sl_new[b] += 1
    rep = [f"Wikidata artists with a MusicBrainz ID and at least {a.min_sitelinks} sitelinks: {len(rows):,}",
           f"Time: {time.time() - t0:,.0f} s", "",
           "Sitelinks >= N | artists | with a genre that maps to Soundlore | of those, not yet in the artist layer"]
    for n in (2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 30, 50):
        c = lambda C: sum(v for k, v in C.items() if k >= n)
        rep.append(f"  N >= {n:>3}   {c(by_sl):>8,}   {c(by_sl_g):>8,}   {c(by_sl_new):>8,}")
    rep += ["", "Reference artists (name, sitelinks, in the artist layer now, genres mapped / total, description):"]
    for b in refs:
        mbid = val(b, "mbid"); g = val(b, "genres").split()
        rep.append(f"  {val(b, 'name'):<22} {val(b, 'sl'):>4}  {'yes' if mbid in sel else 'no ':<3}  "
                   f"{sum(1 for q in g if mapped(q))}/{len(g)}  {val(b, 'desc')[:60]}")
    text = "\n".join(rep)
    print("\n" + text)
    open(os.path.join(OUT, "wikidata_counts.txt"), "w", encoding="utf-8").write(text + "\n")


if __name__ == "__main__":
    main()
