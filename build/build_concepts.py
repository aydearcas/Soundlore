"""Build the concept thesaurus (SKOS-like JSON) from concepts/*.txt.

Each concept gets a MeSH-style tree number (e.g. RHY.01.03.02).
All relations are checked against existing concepts.
"""
import json, sys, glob, os
from collections import OrderedDict, Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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
        c["tree"] = tree[c["id"]]
        c["prompt_adherence_expected"] = ADHERENCE_OVERRIDE.get(c["id"], ADHERENCE[c["facet"]])
        c["prompt_adherence_tested"] = None
    out = {"facets": facets, "concepts": [{k: v for k, v in c.items() if not k.startswith("_")} for c in concepts]}
    json.dump(out, open(os.path.join(ROOT, "build", "concepts.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("Concepts:", len(concepts), dict(Counter(c["facet"] for c in concepts)))

if __name__ == "__main__":
    main()
