"""Fetch from Wikidata the Wikipedia articles and the start years of artists and genres.

For the artist and genre records (links to the English and Spanish Wikipedia) and for the future
timeline (when each artist and genre appeared). Wikidata is CC0; Wikipedia articles are only linked.
Runs on a computer with internet access (the Wikidata Query Service), standard library only.

Usage:  python build/fetch_wikidata_extras.py

Output (sources/wikidata/):
  artists_extras.tsv.gz   mbid, enwiki URL, eswiki URL, work period start (P2031), inception (P571), birth (P569)
  genres_extras.tsv       genre key, qid, enwiki URL, eswiki URL, inception (P571), start time (P580)
  extras_counts.txt       how many have each field
Years are the earliest value when an item has several; negative years are BCE.
"""
import gzip, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_wikidata_artists import sparql, val, HEX  # same endpoint, retries and timeouts

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "sources", "wikidata")

Q_ART = """SELECT ?mbid (SAMPLE(?en) AS ?enwiki) (SAMPLE(?es) AS ?eswiki) (MIN(?ws) AS ?work) (MIN(?inc) AS ?incep) (MIN(?b) AS ?birth) WHERE {
  ?item wdt:P434 ?mbid . FILTER(STRSTARTS(?mbid, "%s"))
  ?item wikibase:sitelinks ?sl . FILTER(?sl >= 1)
  OPTIONAL { ?en schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> . }
  OPTIONAL { ?es schema:about ?item ; schema:isPartOf <https://es.wikipedia.org/> . }
  OPTIONAL { ?item wdt:P2031 ?ws . }
  OPTIONAL { ?item wdt:P571 ?inc . }
  OPTIONAL { ?item wdt:P569 ?b . }
} GROUP BY ?mbid"""

Q_GEN = """SELECT ?g (SAMPLE(?en) AS ?enwiki) (SAMPLE(?es) AS ?eswiki) (MIN(?inc) AS ?incep) (MIN(?st) AS ?start) WHERE {
  VALUES ?g { %s }
  OPTIONAL { ?en schema:about ?g ; schema:isPartOf <https://en.wikipedia.org/> . }
  OPTIONAL { ?es schema:about ?g ; schema:isPartOf <https://es.wikipedia.org/> . }
  OPTIONAL { ?g wdt:P571 ?inc . }
  OPTIONAL { ?g wdt:P580 ?st . }
} GROUP BY ?g"""


def year(v):
    """'1984-05-01T00:00:00Z' -> 1984; '-0500-01-01T00:00:00Z' -> -500; '' -> ''"""
    if not v:
        return ""
    neg = v.startswith("-")
    try:
        y = int(v.lstrip("-+").split("-")[0])
    except ValueError:
        return ""
    return str(-y if neg else y)


def main():
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    # --- artists, by MusicBrainz ID prefix (split further when a query times out)
    rows, todo = {}, list(HEX)
    while todo:
        p = todo.pop(0)
        try:
            res = sparql(Q_ART % p)
        except TimeoutError:
            print(f"  prefix {p}: timed out, splitting", flush=True)
            todo = [p + h for h in HEX] + todo
            continue
        for b in res:
            rows[val(b, "mbid")] = (val(b, "enwiki"), val(b, "eswiki"), year(val(b, "work")), year(val(b, "incep")), year(val(b, "birth")))
        print(f"  artists, prefix {p:<3} {len(res):>7,} rows   total {len(rows):>8,}   {time.time() - t0:,.0f} s", flush=True)
        time.sleep(1)
    with gzip.open(os.path.join(OUT, "artists_extras.tsv.gz"), "wt", encoding="utf-8") as f:
        f.write("mbid\tenwiki\teswiki\twork_start\tinception\tbirth\n")
        for m, r in sorted(rows.items()):
            f.write(m + "\t" + "\t".join(r) + "\n")

    # --- genres with a Wikidata item
    G = json.load(open(os.path.join(ROOT, "build", "genres.json"), encoding="utf-8"))
    byq = {}
    for g in G:
        if g.get("wikidata"):
            byq.setdefault(g["wikidata"], []).append(g["key"])
    qs = sorted(byq)
    grows = {}
    for i in range(0, len(qs), 200):
        for b in sparql(Q_GEN % " ".join("wd:" + q for q in qs[i:i + 200])):
            q = val(b, "g").rsplit("/", 1)[-1]
            grows[q] = (val(b, "enwiki"), val(b, "eswiki"), year(val(b, "incep")), year(val(b, "start")))
        print(f"  genres {min(i + 200, len(qs)):,}/{len(qs):,}", flush=True)
        time.sleep(1)
    with open(os.path.join(OUT, "genres_extras.tsv"), "w", encoding="utf-8") as f:
        f.write("key\tqid\tenwiki\teswiki\tinception\tstart_time\n")
        for q in qs:
            r = grows.get(q, ("", "", "", ""))
            for k in byq[q]:
                f.write(f"{k}\t{q}\t" + "\t".join(r) + "\n")

    c = lambda R, k: sum(1 for r in R.values() if r[k])
    rep = [f"Artists with a MusicBrainz ID and at least one sitelink: {len(rows):,}",
           f"  English Wikipedia {c(rows, 0):,} · Spanish Wikipedia {c(rows, 1):,} · work period start {c(rows, 2):,} · inception {c(rows, 3):,} · birth {c(rows, 4):,}",
           f"Genres with a Wikidata item: {len(qs):,}",
           f"  English Wikipedia {c(grows, 0):,} · Spanish Wikipedia {c(grows, 1):,} · inception {c(grows, 2):,} · start time {c(grows, 3):,}",
           f"Time: {time.time() - t0:,.0f} s"]
    text = "\n".join(rep)
    print("\n" + text)
    open(os.path.join(OUT, "extras_counts.txt"), "w", encoding="utf-8").write(text + "\n")


if __name__ == "__main__":
    main()
