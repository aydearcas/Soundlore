"""Stable Soundlore identifiers (SL000001, SL000002, ...) for the concepts.

The registry `concepts/ids.tsv` is the authority: one row per identifier ever issued.
An identifier is never edited, renumbered or reused, so it survives reordering,
relabeling and moving a concept to another branch or file.

Build behavior (called from build_concepts.py):
  - concepts that are already registered keep their identifier;
  - new concepts get the next free number, appended to the registry;
  - if a registered, active slug is missing from the sources, the build stops
    before issuing anything, because the concept was either renamed or deleted
    and a new identifier must not be issued by mistake.

Command line:
  python build/ids.py check               validate the registry against the sources
  python build/ids.py rename OLD NEW      rename a concept slug everywhere, keeping its identifier
  python build/ids.py retire SLUG         mark the identifier of a deleted concept as retired
  python build/ids.py split OLD KEEP NEW [NEW ...]
                                          split a concept: KEEP (OLD itself, or a new slug for it) keeps the
                                          identifier; each NEW concept, already written in concepts/*.txt,
                                          gets a new identifier. Nothing that pointed to OLD is moved: every
                                          reference (relations, entry terms, genre profiles, side tables) is
                                          listed in work/splits/ for manual reassignment.
"""
import csv, glob, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY = os.path.join(ROOT, "concepts", "ids.tsv")
PREFIX, DIGITS = "SL", 6
UID_RE = re.compile(rf"^{PREFIX}\d{{{DIGITS}}}$")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
HEADER = ["uid", "slug", "status", "note"]
STATUSES = {"active", "retired"}


class IdError(Exception):
    pass


def load():
    """Registry rows as dicts, in file order."""
    if not os.path.exists(REGISTRY):
        return []
    rows = []
    with open(REGISTRY, encoding="utf-8", newline="") as f:
        lines = [ln for ln in f if ln.strip() and not ln.startswith("#")]
    reader = csv.reader(lines, delimiter="\t")
    head = next(reader, None)
    if head != HEADER:
        raise IdError(f"{REGISTRY}: unexpected header {head}")
    for n, r in enumerate(reader, 2):
        r = (r + [""] * len(HEADER))[:len(HEADER)]
        rows.append(dict(zip(HEADER, r)))
    seen_uid, seen_slug = set(), set()
    for r in rows:
        if not UID_RE.match(r["uid"]):
            raise IdError(f"Malformed identifier in registry: {r['uid']!r}")
        if r["status"] not in STATUSES:
            raise IdError(f"{r['uid']}: unknown status {r['status']!r}")
        if r["uid"] in seen_uid:
            raise IdError(f"Duplicate identifier in registry: {r['uid']}")
        seen_uid.add(r["uid"])
        if r["status"] == "active":
            if r["slug"] in seen_slug:
                raise IdError(f"Slug registered twice as active: {r['slug']}")
            seen_slug.add(r["slug"])
    return rows


def save(rows):
    with open(REGISTRY, "w", encoding="utf-8", newline="") as f:
        f.write("# Soundlore stable concept identifiers. Never edit, renumber or reuse an identifier.\n")
        f.write("# Rename a slug with `python build/ids.py rename OLD NEW`; retire a deleted concept with `python build/ids.py retire SLUG`.\n")
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(HEADER)
        for r in rows:
            w.writerow([r[k] for k in HEADER])


def next_number(rows):
    return max((int(r["uid"][len(PREFIX):]) for r in rows), default=0) + 1


def assign(slugs, write=True):
    """Map every slug (in source order) to its identifier, issuing new ones if needed."""
    rows = load()
    active = {r["slug"]: r["uid"] for r in rows if r["status"] == "active"}
    missing = [s for s in active if s not in set(slugs)]
    if missing:
        raise IdError(
            "Registered concepts missing from concepts/*.txt: " + ", ".join(missing) +
            "\nIf a concept was renamed, run `python build/ids.py rename OLD NEW` (it keeps the identifier)."
            "\nIf it was deleted on purpose, run `python build/ids.py retire SLUG`.")
    n, issued = next_number(rows), []
    for s in slugs:
        if s not in active:
            uid = f"{PREFIX}{n:0{DIGITS}d}"
            n += 1
            rows.append({"uid": uid, "slug": s, "status": "active", "note": ""})
            active[s] = uid
            issued.append((uid, s))
    if issued and write:
        save(rows)
    return active, issued


# ---------- command line

def source_slugs():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from build_concepts import parse_file
    slugs = []
    for f in sorted(glob.glob(os.path.join(ROOT, "concepts", "*.txt"))):
        slugs += [c["id"] for c in parse_file(f)[1]]
    return slugs


def cmd_check():
    rows = load()
    slugs = source_slugs()
    active = {r["slug"] for r in rows if r["status"] == "active"}
    new = [s for s in slugs if s not in active]
    gone = [s for s in active if s not in set(slugs)]
    print(f"{len(rows)} identifiers issued, {len(active)} active, {len(rows) - len(active)} retired")
    if new:
        print("Not yet registered (the next build will issue identifiers):", ", ".join(new))
    if gone:
        print("Registered but missing from the sources:", ", ".join(gone))
        return 1
    return 0


def _replace_word(text, old, new):
    """Replace a whole slug token (slugs are [a-z0-9_]; '-' and '@' are not part of them)."""
    return re.sub(rf"(?<![A-Za-z0-9_@-]){re.escape(old)}(?![A-Za-z0-9_-])", new, text)


def _rewrite(path, fn):
    with open(path, encoding="utf-8", newline="") as f:
        before = f.read()
    after = fn(before)
    if after != before:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(after)
        return True
    return False


def cmd_rename(old, new):
    if not SLUG_RE.match(new):
        raise IdError(f"Invalid slug {new!r}: use lowercase letters, digits and single underscores")
    rows = load()
    by_slug = {r["slug"]: r for r in rows if r["status"] == "active"}
    if old not in by_slug:
        raise IdError(f"{old!r} is not an active registered slug")
    if new in by_slug:
        raise IdError(f"{new!r} is already used by {by_slug[new]['uid']}")
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from profiles import tokenize
    changed = []
    GENRES = set()

    def concept_file(text):
        out = []
        for line in text.splitlines(keepends=True):
            if line.lstrip().startswith(("#", "@")) or "|" not in line:
                out.append(line); continue
            parts = line.split("|")
            lead = parts[0][:len(parts[0]) - len(parts[0].lstrip())]
            if parts[0].strip() == old:
                parts[0] = parts[0].replace(old, new, 1)
            if len(parts) >= 6:  # relations field (last), keeping its line ending
                parts[5] = _replace_word(parts[5], old, new)
            out.append("|".join(parts))
        return "".join(out)

    for f in sorted(glob.glob(os.path.join(ROOT, "concepts", "*.txt"))):
        if _rewrite(f, concept_file):
            changed.append(f)

    # genre profiles: only tokens that the profile parser reads as concepts
    def profile_file(text):
        out = []
        for line in text.splitlines(keepends=True):
            if line.strip().startswith("#") or not re.search(rf"(?<![A-Za-z0-9_@-]){re.escape(old)}(?![A-Za-z0-9_-])", line):
                out.append(line); continue
            sep = " += " if " += " in line else " = "
            name, rhs = line.split(sep, 1)
            end = rhs[len(rhs.rstrip("\r\n")):]
            parts = []
            for part in rhs.rstrip("\r\n").split("|"):
                words = part.split()
                if not words:
                    parts.append(part); continue
                lvl, toks = words[0], tokenize(" ".join(words[1:]), {old}, GENRES)
                body = " ".join(("@" + t if k == "@" else new if (k == "c" and t == old) else ("@" + t if k == "?@" else t)) for k, t in toks)
                lead = part[:len(part) - len(part.lstrip())]
                trail = part[len(part.rstrip()):]
                parts.append(f"{lead}{lvl} {body}{trail}" if body else f"{lead}{lvl}{trail}")
            out.append(name + sep + "|".join(parts) + end)
        return "".join(out)

    from profiles import load_raw
    GENRES = set(load_raw())  # same name set the profile parser uses for @inheritance
    for f in sorted(glob.glob(os.path.join(ROOT, "genres", "profiles_*.txt"))):
        if _rewrite(f, profile_file):
            changed.append(f)

    # side tables keyed by slug (first column) or carrying it as a readable column
    def first_col(text):
        return "".join((new + ln[len(old):]) if ln.split("|")[0].strip() == old and ln.startswith(old) else ln
                       for ln in text.splitlines(keepends=True))
    tr = os.path.join(ROOT, "concepts", "translations_es.tsv")
    if os.path.exists(tr) and _rewrite(tr, first_col):
        changed.append(tr)
    uid = by_slug[old]["uid"]
    for name in ("definitions_en.tsv", "wikidata.tsv"):
        p = os.path.join(ROOT, "concepts", name)
        if os.path.exists(p) and _rewrite(p, lambda t: "".join(
                ln.replace(f"{uid}\t{old}\t", f"{uid}\t{new}\t", 1) for ln in t.splitlines(keepends=True))):
            changed.append(p)
    # quoted slugs in scripts and the viewer (e.g. per-concept overrides, default selection)
    for p in sorted(glob.glob(os.path.join(ROOT, "build", "*.py"))) + sorted(glob.glob(os.path.join(ROOT, "viewer", "*.html"))):
        if os.path.basename(p) == "ids.py":
            continue
        if _rewrite(p, lambda t: t.replace(f'"{old}"', f'"{new}"').replace(f"'{old}'", f"'{new}'")):
            changed.append(p)

    by_slug[old]["slug"] = new
    note = by_slug[old]["note"]
    by_slug[old]["note"] = (note + "; " if note else "") + f"renamed from {old}"
    save(rows)
    print(f"{uid}: {old} -> {new}")
    for p in changed:
        print("  updated", os.path.relpath(p, ROOT))
    print("Rebuild to propagate: build_concepts.py, export_skos.py, build_genres.py, then sync_viewer.py (and build_map.py if you keep the map in sync).")


def cmd_retire(slug):
    rows = load()
    hit = [r for r in rows if r["status"] == "active" and r["slug"] == slug]
    if not hit:
        raise IdError(f"{slug!r} is not an active registered slug")
    if slug in source_slugs():
        raise IdError(f"{slug!r} still exists in concepts/*.txt; delete the concept first")
    hit[0]["status"] = "retired"
    save(rows)
    print(f"{hit[0]['uid']} ({slug}) retired; the identifier will never be reused")


def cmd_split(old, keep, news):
    """Split OLD into KEEP (keeps the identifier) and NEW concepts (new identifiers).

    The NEW concepts must already be in concepts/*.txt, so that their place, label and relations are an
    editorial decision, not a side effect. References to the old concept are reported, never moved."""
    import datetime
    rows = load()
    by_slug = {r["slug"]: r for r in rows if r["status"] == "active"}
    if old not in by_slug:
        raise IdError(f"{old!r} is not an active registered slug")
    if not news:
        raise IdError("give at least one NEW concept")
    for n in news:
        if not SLUG_RE.match(n):
            raise IdError(f"Invalid slug {n!r}")
        if n in by_slug:
            raise IdError(f"{n!r} is already registered ({by_slug[n]['uid']}); a split creates new concepts")
    if len(set(news + [keep])) != len(news) + 1:
        raise IdError("KEEP and NEW slugs must all be different")
    if keep != old:
        cmd_rename(old, keep)
        rows = load()
        by_slug = {r["slug"]: r for r in rows if r["status"] == "active"}
    present = set(source_slugs())
    missing = [n for n in news + [keep] if n not in present]
    if missing:
        raise IdError("Write these concepts in concepts/*.txt first: " + ", ".join(missing))
    uid = by_slug[keep]["uid"]
    today = datetime.date.today().isoformat()
    n, issued = next_number(rows), []
    for slug in news:
        nu = f"{PREFIX}{n:0{DIGITS}d}"; n += 1
        rows.append({"uid": nu, "slug": slug, "status": "active", "note": f"split from {uid} ({old}) {today}"})
        issued.append((nu, slug))
    r = by_slug[keep]
    r["note"] = (r["note"] + "; " if r["note"] else "") + f"split {today}: " + ", ".join(f"{u} {s}" for u, s in issued)
    save(rows)

    # references to review: anything that names the kept slug may have meant one of the new parts
    pat = re.compile(rf"(?<![A-Za-z0-9_@-]){re.escape(keep)}(?![A-Za-z0-9_-])")
    refs = []
    for f in sorted(glob.glob(os.path.join(ROOT, "concepts", "*.txt"))):
        for ln, line in enumerate(open(f, encoding="utf-8"), 1):
            if line.lstrip().startswith("#") or "|" not in line:
                continue
            parts = [p.strip() for p in line.split("|")]
            if parts[0] == keep:
                if parts[2]:
                    refs.append(("entry terms", f"{os.path.basename(f)}:{ln}", parts[2]))
                if len(parts) > 4 and parts[4]:
                    refs.append(("prompt terms", f"{os.path.basename(f)}:{ln}", parts[4]))
                if len(parts) > 5 and parts[5]:
                    refs.append(("own relations", f"{os.path.basename(f)}:{ln}", parts[5]))
            elif len(parts) > 5 and pat.search(parts[5]):
                refs.append(("relation", f"{os.path.basename(f)}:{ln}", f"{parts[0]} -> {keep}"))
    for f in sorted(glob.glob(os.path.join(ROOT, "genres", "profiles_*.txt"))):
        for ln, line in enumerate(open(f, encoding="utf-8"), 1):
            if not line.strip().startswith("#") and pat.search(line):
                refs.append(("genre profile", f"{os.path.basename(f)}:{ln}", line.split("=")[0].strip().rstrip("+").strip()))
    for name in ("definitions_en.tsv", "wikidata.tsv", "musicbrainz_instruments.tsv", "translations_es.tsv"):
        p = os.path.join(ROOT, "concepts", name)
        if os.path.exists(p):
            for ln, line in enumerate(open(p, encoding="utf-8"), 1):
                if line.startswith(uid + "\t") or line.split("\t")[0] == keep:
                    refs.append(("side table", f"{name}:{ln}", line.rstrip("\n").split("\t")[2][:90] if "\t" in line else ""))
    out_dir = os.path.join(ROOT, "work", "splits")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"{today}_{keep}.tsv")
    with open(out, "w", encoding="utf-8", newline="") as f:
        f.write(f"# Split of {uid} ({old}) on {today}. Kept: {uid} {keep}. New: " + ", ".join(f"{u} {s}" for u, s in issued) + "\n")
        f.write("# Review each reference and reassign it by hand where it meant one of the new concepts. Fill in 'decision'.\n")
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(["kind", "where", "content", "decision"])
        for k, where, content in refs:
            w.writerow([k, where, content, ""])
    print(f"{uid} keeps '{keep}'; new: " + ", ".join(f"{u} {s}" for u, s in issued))
    print(f"{len(refs)} references to review -> {os.path.relpath(out, ROOT)}")
    for k, where, content in refs:
        print(f"  {k:14} {where:32} {content}")


if __name__ == "__main__":
    a = sys.argv[1:]
    try:
        if a == ["check"]:
            sys.exit(cmd_check())
        elif len(a) == 3 and a[0] == "rename":
            cmd_rename(a[1], a[2])
        elif len(a) == 2 and a[0] == "retire":
            cmd_retire(a[1])
        elif len(a) >= 4 and a[0] == "split":
            cmd_split(a[1], a[2], a[3:])
        else:
            print(__doc__); sys.exit(2)
    except IdError as e:
        print("ERROR:", e); sys.exit(1)
