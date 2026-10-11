"""Compile Claude's proposals (batch_NN.txt, compact syntax) into low_genres_batch_NN_claude.tsv and validate them.

Line syntax:  genre ; confidence ; C a b | F c | O d | X e ; rationale
A line without any concept is written as NO_CHANGE. 'mb:name' refers to a MusicBrainz instrument
not yet in Soundlore (spaces as underscores), written as its MB code.
"""
import csv, json, os, re, sys, unicodedata
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
CP = os.path.join(ROOT, "work", "chatgpt_profiles")
concepts = {c["id"]: c for c in json.load(open(os.path.join(ROOT, "build", "concepts.json"), encoding="utf-8"))["concepts"]}
norm = lambda s: unicodedata.normalize("NFC", s).lower().replace("_", " ").strip()
mb = {}
for r in csv.DictReader(open(os.path.join(CP, "musicbrainz_instruments_candidates.tsv"), encoding="utf-8"), delimiter="\t"):
    mb.setdefault(norm(r["name"]), []).append(r)
LEVEL = {"characteristic": "C", "frequent": "F", "occasional": "O"}

def run(n):
    batch = list(csv.DictReader(open(os.path.join(CP, f"low_genres_batch_{n:02d}.tsv"), encoding="utf-8"), delimiter="\t"))
    current = {b["genre"]: {c for k in LEVEL for c in b[k].split()} for b in batch}
    rows, errors, seen = [], [], set()
    for ln, line in enumerate(open(os.path.join(HERE, f"batch_{n:02d}.txt"), encoding="utf-8"), 1):
        if not line.strip() or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.rstrip("\n").split(";")]
        if len(parts) < 4:
            errors.append(f"{ln}: expected 4 fields"); continue
        genre, conf, body, why = parts[0], parts[1], parts[2], ";".join(parts[3:]).strip()
        if genre not in current:
            errors.append(f"{ln}: unknown genre {genre!r}"); continue
        if genre in seen:
            errors.append(f"{ln}: duplicate genre {genre!r}")
        seen.add(genre)
        props = []
        for seg in body.split("|"):
            toks = seg.split()
            if not toks:
                continue
            lvl, items = toks[0], toks[1:]
            if lvl not in ("C", "F", "O", "X"):
                errors.append(f"{ln}: bad level {lvl!r}"); continue
            for t in items:
                if t.startswith("mb:"):
                    hit = mb.get(norm(t[3:]))
                    if not hit:
                        errors.append(f"{ln} {genre}: unknown MusicBrainz instrument {t}"); continue
                    if len(hit) > 1:
                        errors.append(f"{ln} {genre}: ambiguous MusicBrainz name {t}"); continue
                    if lvl not in ("C", "F"):
                        errors.append(f"{ln} {genre}: MB code at level {lvl}"); continue
                    props.append((hit[0]["code"], lvl))
                else:
                    if t not in concepts:
                        errors.append(f"{ln} {genre}: unknown concept {t}"); continue
                    if lvl == "X" and t not in current[genre]:
                        errors.append(f"{ln} {genre}: X on {t}, which is not in the profile"); continue
                    if lvl != "X" and t in current[genre]:
                        errors.append(f"{ln} {genre}: {t} is already in the profile"); continue
                    props.append((t, lvl))
        ids = [p[0] for p in props]
        if len(ids) != len(set(ids)):
            errors.append(f"{ln} {genre}: concept listed twice")
        if not props:
            rows.append([genre, "NO_CHANGE", "", "", why])
        for cid, lvl in props:
            rows.append([genre, cid, lvl, conf, why])
    missing = [g for g in current if g not in seen]
    if missing:
        errors.append("genres not covered: " + ", ".join(missing))
    return rows, errors

if __name__ == "__main__":
    total_err = 0
    for n in [int(a) for a in sys.argv[1:]]:
        rows, errors = run(n)
        print(f"batch {n:02d}: {len(rows)} rows, {len(errors)} problems")
        for e in errors:
            print("  ", e)
        total_err += len(errors)
        if not errors:
            with open(os.path.join(CP, f"low_genres_batch_{n:02d}_claude.tsv"), "w", encoding="utf-8", newline="") as f:
                w = csv.writer(f, delimiter="\t", lineterminator="\n")
                w.writerow(["genre", "concept_id", "level", "confidence", "rationale"])
                w.writerows(rows)
    sys.exit(1 if total_err else 0)
