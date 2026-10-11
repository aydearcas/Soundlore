"""Stream the MusicBrainz artist JSON dump and keep the artists that have community-voted genres.

Runs on the computer that holds the dump, with the standard library only. The archive is read as a
stream (tar inside xz), so nothing is decompressed to disk; expect 10-30 minutes for the ~1.7 GB dump.

Usage:
  python build/filter_artists.py                       # default paths below
  python build/filter_artists.py DUMP.tar.xz OUT.jsonl.gz
  python build/filter_artists.py --also sources/wikidata/artist_mbids.txt
      also keep the artists listed in that file (one MBID per line) even without genre votes;
      used for the artists whose genres come from Wikidata (build/fetch_wikidata_artists.py)

Input:  sources/musicbrainz/artist.tar.xz  (https://data.metabrainz.org/pub/musicbrainz/data/json-dumps/)
Output: sources/musicbrainz/artist_genres_extract.jsonl.gz, one artist per line:
  {"id": MBID, "name", "sort", "type", "gender", "dis": disambiguation,
   "area", "cc": ISO country code of the area, "begin", "end", "ended",
   "wd": Wikidata QID or null, "rv": rating votes, "g": [[genre MBID, votes], ...]}
  sources/musicbrainz/artist_genres_extract.meta.json: dump timestamp, counts and license notice.
  sources/musicbrainz/artist_genres_counts.txt: counts by vote threshold, to choose the cut-off.

License: artist names, areas and dates are MusicBrainz core data (CC0). The artist-genre votes come
from MusicBrainz genres/tags and are CC BY-NC-SA 3.0; the extract carries that notice.
"""
import argparse, gzip, io, json, os, re, sys, tarfile, time
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "sources", "musicbrainz", "artist.tar.xz")
OUT = os.path.join(ROOT, "sources", "musicbrainz", "artist_genres_extract.jsonl.gz")
HAS_GENRE = re.compile(rb'"genres"\s*:\s*\[\s*\{')
ANY_ID = re.compile(rb'"id"\s*:\s*"([0-9a-f-]{36})"')
QID = re.compile(r"wikidata\.org/wiki/(Q\d+)")
LICENSE = ("Derived from the MusicBrainz artist JSON dump. Artist core data: CC0. "
           "Artist-genre votes (field g): MusicBrainz genres/tags, CC BY-NC-SA 3.0, https://musicbrainz.org/doc/About/Data_License")


def slim(a):
    area = a.get("area") or {}
    ls = a.get("life-span") or {}
    wd = None
    for r in a.get("relations") or []:
        if r.get("type") == "wikidata":
            m = QID.search(((r.get("url") or {}).get("resource")) or "")
            if m:
                wd = m.group(1); break
    cc = (area.get("iso-3166-1-codes") or [None])[0] or a.get("country")
    g = sorted(([x["id"], x.get("count", 0)] for x in a.get("genres") or [] if x.get("id")), key=lambda t: -t[1])
    return {"id": a["id"], "name": a.get("name"), "sort": a.get("sort-name"), "type": a.get("type"),
            "gender": a.get("gender"), "dis": a.get("disambiguation") or None,
            "area": area.get("name"), "cc": cc, "begin": ls.get("begin"), "end": ls.get("end"),
            "ended": bool(ls.get("ended")), "wd": wd,
            "rv": ((a.get("rating") or {}).get("votes-count")) or 0, "g": g}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", nargs="?", default=SRC)
    ap.add_argument("out", nargs="?", default=OUT)
    ap.add_argument("--also", help="file of MBIDs to keep even without genre votes")
    args = ap.parse_args()
    src, out = args.src, args.out
    also = set()
    if args.also:
        also = {l.strip().encode() for l in open(args.also, encoding="utf-8") if l.strip()}
        print(f"also keeping {len(also):,} listed artists", flush=True)
    extra = 0
    if not os.path.exists(src):
        sys.exit(f"Dump not found: {src}")
    t0 = time.time()
    seen = kept = 0
    dump = None
    top = Counter()      # artists by the votes of their best-voted genre
    total = Counter()    # artists by the sum of their genre votes
    tmp = out + ".part"
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with tarfile.open(src, mode="r|xz") as tar, gzip.open(tmp, "wt", encoding="utf-8", compresslevel=6) as fo:
        for m in tar:
            name = m.name.replace("\\", "/")
            if not m.isfile():
                continue
            if name.endswith("TIMESTAMP"):
                dump = tar.extractfile(m).read().decode("utf-8", "replace").strip()
                print("dump timestamp:", dump, flush=True)
                continue
            if not name.endswith("mbdump/artist"):
                continue
            print(f"reading {name} ({m.size / 1e9:.1f} GB uncompressed)", flush=True)
            f = io.BufferedReader(tar.extractfile(m), buffer_size=1 << 20)
            for line in f:
                seen += 1
                if seen % 200000 == 0:
                    print(f"  {seen:>9,} artists read, {kept:,} with genres, {time.time() - t0:,.0f} s", flush=True)
                if not HAS_GENRE.search(line):
                    if not also or not any(i in also for i in ANY_ID.findall(line)):
                        continue
                    a = slim(json.loads(line))
                    if a["id"].encode() not in also:
                        continue
                    extra += 1
                    fo.write(json.dumps(a, ensure_ascii=False, separators=(",", ":")) + "\n")
                    continue
                a = slim(json.loads(line))
                if not a["g"]:
                    if a["id"].encode() in also:
                        extra += 1
                        fo.write(json.dumps(a, ensure_ascii=False, separators=(",", ":")) + "\n")
                    continue
                kept += 1
                top[min(a["g"][0][1], 20)] += 1
                total[min(sum(v for _, v in a["g"]), 50)] += 1
                fo.write(json.dumps(a, ensure_ascii=False, separators=(",", ":")) + "\n")
    os.replace(tmp, out)
    meta = {"dump": dump, "artists_read": seen, "artists_with_genres": kept, "listed_without_genres": extra, "license": LICENSE}
    json.dump(meta, open(out.replace(".jsonl.gz", "") + ".meta.json", "w", encoding="utf-8"), indent=1)

    rep = [f"MusicBrainz artist dump {dump}: {seen:,} artists read, {kept:,} with at least one genre vote.",
           f"Listed artists kept without genre votes: {extra:,}.",
           f"Time: {time.time() - t0:,.0f} s. Output: {out} ({os.path.getsize(out) / 1e6:.1f} MB)", "",
           "Artists whose best-voted genre has at least N votes:"]
    acc = 0
    for n in range(20, 0, -1):
        acc += top[n]
        if n in (1, 2, 3, 4, 5, 7, 10, 15, 20):
            rep.append(f"  N >= {n:>2}{'+' if n == 20 else ' '}: {acc:>9,}")
    rep += ["", "Artists whose genre votes add up to at least N:"]
    acc = 0
    for n in range(50, 0, -1):
        acc += total[n]
        if n in (1, 2, 3, 5, 10, 20, 50):
            rep.append(f"  N >= {n:>2}{'+' if n == 50 else ' '}: {acc:>9,}")
    text = "\n".join(rep)
    print("\n" + text)
    open(os.path.join(os.path.dirname(out), "artist_genres_counts.txt"), "w", encoding="utf-8").write(text + "\n")


if __name__ == "__main__":
    main()
