"""Build the Soundlore concept thesaurus (SKOS-like JSON) from concepts/*.txt.

Each concept gets a stable identifier (SL000123, see build/ids.py) and a MeSH-style
tree number (e.g. RHY.01.03.02). All relations are checked against existing concepts.
Definitions (concepts/definitions_en.tsv) and Wikidata links (concepts/wikidata.tsv)
are joined by identifier.
"""
import json, sys, glob, os, re
from collections import OrderedDict, Counter
from urllib.parse import quote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION = "0.9"
# Base for concept URIs in the SKOS export. Change it once Soundlore has a permanent web address
# (e.g. "https://<host>/id/"); identifiers stay the same, only the prefix changes.
BASE_URI = "urn:soundlore:"
MATCHES = {"exact", "close", "broad", "narrow", "related"}
DEF_STATUSES = {"draft", "reviewed"}

# Untested estimate of how reliably music generators follow prompt terms of each facet.
ADHERENCE = {
    "RHY": "low", "DRM": "medium", "HAR": "low", "SCL": "low", "MEL": "medium",
    "FRM": "medium", "TEX": "low", "VOC": "high", "INS": "high", "TEC": "medium",
    "PRD": "high", "DYN": "medium", "LYR": "medium", "MOO": "high",
}
# Known or very likely exceptions
ADHERENCE_OVERRIDE = {
    "tempo": "medium", "tempo_very_slow": "medium", "tempo_slow": "medium", "tempo_mid": "medium",
    "tempo_fast": "medium", "tempo_very_fast": "medium", "swing": "medium", "shuffle": "medium",
    "half_time": "medium", "time_3_4": "medium", "time_6_8": "medium",
    "blast_beat": "high", "double_kick": "high", "four_on_the_floor": "high", "trap_beat": "high",
    "breakbeat": "high", "dembow": "high", "boom_bap": "high",
    "song_section": "high", "intro": "high", "verse": "high", "chorus": "high", "bridge": "high",
    "pre_chorus": "high", "outro": "high", "drop": "high", "build_up": "high",
    "breakdown_metal": "high", "breakdown_edm": "high", "solo_section": "high", "guitar_solo": "high",
    "instrumental_break": "high", "fade_out": "medium",
    "a_cappella": "medium", "call_and_response": "medium",
    "truck_driver_modulation": "medium", "modulation": "low",
    "fugue": "low", "canon": "low", "counterpoint": "low",
    "minor_key": "medium", "major_key": "medium",
    "instrumental_track": "high",
}

def parse_file(path):
    facets, concepts = [], []
    facet = None
    stack = []  # (indent, id)
    for ln, raw in enumerate(open(path, encoding="utf-8"), 1):
        line = raw.rstrip("\n")
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith("@"):
            code, label = [x.strip() for x in line[1:].split("|")]
            facet = code
            facets.append({"code": code, "label": label})
            stack = []
            continue
        indent = (len(line) - len(line.lstrip(" "))) // 2
        parts = [p.strip() for p in line.strip().split("|")]
        while len(parts) < 6:
            parts.append("")
        cid, term, syn, note, prompt, rel = parts[:6]
        while stack and stack[-1][0] >= indent:
            stack.pop()
        parent = stack[-1][1] if stack else None
        stack.append((indent, cid))
        broader = [parent] if parent else []
        related = []
        for r in [x.strip() for x in rel.split(",") if x.strip()]:
            if r.startswith("^"):
                broader.append(r[1:])
            else:
                related.append(r)
        prompt_items = [s.strip() for s in prompt.split(";") if s.strip()]
        concepts.append(OrderedDict(
            id=cid, facet=facet, label=term,
            synonyms=[a.strip() for a in syn.split(";") if a.strip()],
            note=note or None, broader=broader, related=related,
            prompt_terms=[s for s in prompt_items if not s.startswith("[")],
            prompt_tags=[s for s in prompt_items if s.startswith("[")],
            _src=f"{os.path.basename(path)}:{ln}",
        ))
    return facets, concepts

def read_tsv(name, header):
    """Rows of a tab-separated side table (no quoting; '#' lines are comments)."""
    path = os.path.join(ROOT, "concepts", name)
    if not os.path.exists(path):
        return []
    lines = [ln.rstrip("\r\n") for ln in open(path, encoding="utf-8") if ln.strip() and not ln.startswith("#")]
    if lines[0].split("\t") != header:
        sys.exit(f"{name}: expected header {header}, found {lines[0].split(chr(9))}")
    rows = []
    for n, ln in enumerate(lines[1:], 2):
        parts = ln.split("\t")
        if len(parts) > len(header):
            sys.exit(f"{name}: too many columns in row {n}: {ln[:80]}")
        rows.append(dict(zip(header, parts + [""] * (len(header) - len(parts)))))
    return rows

def read_facet_md(errors, name="facets_en.md"):
    """Facet descriptions: '## CODE | Label', 'Summary: one sentence', then article paragraphs.
    Returns {code: {label, summary, article}}; the article keeps *emphasis* and blank lines between paragraphs."""
    path = os.path.join(ROOT, "concepts", name)
    if not os.path.exists(path):
        errors.append(f"{name}: file not found"); return {}
    text = re.sub(r"<!--.*?-->", "", open(path, encoding="utf-8").read(), flags=re.S).replace("\r\n", "\n")
    out = {}
    for sec in re.split(r"^## ", text, flags=re.M)[1:]:
        head, _, body = sec.partition("\n")
        if "|" not in head:
            errors.append(f"{name}: heading without 'CODE | Label': {head[:60]}"); continue
        code, label = [x.strip() for x in head.split("|", 1)]
        body = body.strip()
        m = re.match(r"Summary:\s*(.+?)\n\s*\n(.*)", body, flags=re.S)
        if not m:
            errors.append(f"{name}: {code} needs a 'Summary:' line followed by a blank line and the article"); continue
        if code in out:
            errors.append(f"{name}: duplicate section {code}")
        paras = [" ".join(p.split()) for p in re.split(r"\n\s*\n", m.group(2).strip()) if p.strip()]
        out[code] = dict(label=label, summary=" ".join(m.group(1).split()), article="\n\n".join(paras))
    return out

def wiki_url(title):
    return "https://en.wikipedia.org/wiki/" + quote(title.replace(" ", "_"), safe="()',!:;@*$-._~/")

def load_side_tables(uid_by_slug, errors):
    slug_by_uid = {u: s for s, u in uid_by_slug.items()}
    def keyed(name, header):
        out = {}
        for r in read_tsv(name, header):
            u = r["uid"]
            if u not in slug_by_uid:
                errors.append(f"{name}: {u} is not an active concept identifier"); continue
            if r["slug"] != slug_by_uid[u]:
                errors.append(f"{name}: {u} is labeled '{r['slug']}' but the concept is now '{slug_by_uid[u]}'")
            if u in out:
                errors.append(f"{name}: duplicate row for {u}")
            out[u] = r
        return out
    defs = keyed("definitions_en.tsv", ["uid", "slug", "definition", "source", "status"])
    for u, r in defs.items():
        if not r["definition"].strip():
            errors.append(f"definitions_en.tsv: empty definition for {u}")
        if r["status"] not in DEF_STATUSES:
            errors.append(f"definitions_en.tsv: {u} has unknown status '{r['status']}'")
    wd = keyed("wikidata.tsv", ["uid", "slug", "qid", "match", "enwiki", "checked", "note"])
    for u, r in wd.items():
        if not re.fullmatch(r"Q[1-9]\d*", r["qid"]):
            errors.append(f"wikidata.tsv: malformed QID '{r['qid']}' for {u}")
        if r["match"] not in MATCHES:
            errors.append(f"wikidata.tsv: {u} has unknown match '{r['match']}'")
    mbi = keyed("musicbrainz_instruments.tsv", ["uid", "slug", "mbid", "mb_name", "match", "basis"])
    for u, r in mbi.items():
        if not re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", r["mbid"]):
            errors.append(f"musicbrainz_instruments.tsv: malformed MBID '{r['mbid']}' for {u}")
        if r["match"] not in MATCHES:
            errors.append(f"musicbrainz_instruments.tsv: {u} has unknown match '{r['match']}'")
    return defs, wd, mbi

def main():
    facets, concepts = [], []
    for f in sorted(glob.glob(os.path.join(ROOT, "concepts", "*.txt"))):
        fa, co = parse_file(f)
        facets += fa; concepts += co
    by_id, errors = {}, []
    for c in concepts:
        if c["id"] in by_id:
            errors.append(f"Duplicate id: {c['id']} ({c['_src']} and {by_id[c['id']]['_src']})")
        by_id[c["id"]] = c
    for c in concepts:
        for r in c["broader"] + c["related"]:
            if r not in by_id:
                errors.append(f"{c['_src']}: '{c['id']}' points to unknown concept '{r}'")
    if errors:
        print("\n".join(errors)); sys.exit(1)
    # stable identifiers, then the side tables keyed by them
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import ids
    try:
        uid_by_slug, issued = ids.assign([c["id"] for c in concepts])
    except ids.IdError as e:
        sys.exit(f"ERROR: {e}")
    for u, s in issued:
        print(f"New identifier {u} for '{s}' (added to concepts/ids.tsv)")
    defs, wd, mbi = load_side_tables(uid_by_slug, errors)
    # facet descriptions: concepts/facets_en.md (summary + article per facet)
    fdesc = read_facet_md(errors)
    for f in facets:
        r = fdesc.pop(f["code"], None)
        if r is None:
            errors.append(f"facets_en.md: no section for facet {f['code']}")
            f["summary"] = f["article"] = None
            continue
        if r["label"] != f["label"]:
            errors.append(f"facets_en.md: {f['code']} is labeled '{r['label']}' but the concept files say '{f['label']}'")
        f["summary"], f["article"] = r["summary"], r["article"]
        words = len(re.sub(r"[*_]", "", r["article"]).split())
        if not 150 <= words <= 300:
            print(f"Warning: facets_en.md: the {f['code']} article has {words} words (expected 150-300)")
    errors += [f"facets_en.md: unknown facet code {c}" for c in fdesc]
    if errors:
        print("\n".join(errors)); sys.exit(1)
    # make "related" symmetric
    for c in concepts:
        for r in c["related"]:
            if c["id"] not in by_id[r]["related"]:
                by_id[r]["related"].append(c["id"])
    for c in concepts:
        c["narrower"] = []
    for c in concepts:
        for b in c["broader"]:
            by_id[b]["narrower"].append(c["id"])
    # tree numbers: primary hierarchy = first broader term, extra numbers for polyhierarchy
    counters, tree = {}, {}
    for c in concepts:  # file order guarantees the primary parent comes first
        parent = c["broader"][0] if c["broader"] else None
        key = parent or c["facet"]
        counters[key] = counters.get(key, 0) + 1
        prefix = tree[parent][0] if parent else c["facet"]
        tree[c["id"]] = [f"{prefix}.{counters[key]:02d}"]
    for c in concepts:
        for b in c["broader"][1:]:
            counters[b] = counters.get(b, 0) + 1
            tree[c["id"]].append(f"{tree[b][0]}.{counters[b]:02d}")
    for c in concepts:
        u = uid_by_slug[c["id"]]
        d, w = defs.get(u), wd.get(u)
        c["definition"] = d["definition"] if d else None
        c["definition_source"] = d["source"] if d else None
        c["definition_status"] = d["status"] if d else None
        c["wikidata"] = OrderedDict(
            qid=w["qid"], match=w["match"], url=f"https://www.wikidata.org/wiki/{w['qid']}",
            enwiki=w["enwiki"] or None, enwiki_url=wiki_url(w["enwiki"]) if w["enwiki"] else None,
            checked=w["checked"] or None) if w else None
        m = mbi.get(u)
        c["musicbrainz"] = OrderedDict(mbid=m["mbid"], name=m["mb_name"], match=m["match"],
                                       url=f"https://musicbrainz.org/instrument/{m['mbid']}") if m else None
        c["tree"] = tree[c["id"]]
        c["prompt_adherence_expected"] = ADHERENCE_OVERRIDE.get(c["id"], ADHERENCE[c["facet"]])
        c["prompt_adherence_tested"] = None
    FIELDS = ["id", "facet", "label", "synonyms", "definition", "definition_source", "definition_status", "note",
              "broader", "narrower", "related", "tree", "prompt_terms", "prompt_tags",
              "prompt_adherence_expected", "prompt_adherence_tested", "wikidata", "musicbrainz"]
    def record(c):
        assert set(FIELDS) == {k for k in c if not k.startswith("_")}, "update FIELDS"
        r = OrderedDict(uid=uid_by_slug[c["id"]])
        r.update((k, c[k]) for k in FIELDS)
        return r
    out = OrderedDict(scheme=OrderedDict(name="Soundlore", version=VERSION, id_prefix=ids.PREFIX, base_uri=BASE_URI),
                      facets=facets, concepts=[record(c) for c in concepts])
    json.dump(out, open(os.path.join(ROOT, "build", "concepts.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # small summary for the landing page: counts and a sample of records shown as catalog cards
    full = [c for c in out["concepts"] if c["wikidata"] and c["broader"] and c["related"] and c["definition"]]
    by = {c["id"]: c for c in out["concepts"]}
    cards = [OrderedDict(uid=c["uid"], tree=c["tree"][0], label=c["label"], bt=by[c["broader"][0]]["label"],
                         rt=[by[r]["label"] for r in c["related"][:2]], qid=c["wikidata"]["qid"])
             for c in full[::max(1, len(full) // 24)][:24]]
    stats = OrderedDict(version=VERSION, concepts=len(concepts), facets=len(facets),
                        definitions=sum(c["definition"] is not None for c in concepts),
                        wikidata=sum(c["wikidata"] is not None for c in concepts), cards=cards)
    json.dump(stats, open(os.path.join(ROOT, "build", "stats.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("Concepts:", len(concepts), dict(Counter(c["facet"] for c in concepts)))
    print(f"Definitions: {sum(c['definition'] is not None for c in concepts)} | Wikidata links: {sum(c['wikidata'] is not None for c in concepts)}"
          f" ({dict(Counter(c['wikidata']['match'] for c in concepts if c['wikidata']))})"
          f" | MusicBrainz instruments: {sum(c['musicbrainz'] is not None for c in concepts)}")

if __name__ == "__main__":
    main()
