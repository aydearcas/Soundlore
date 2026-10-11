"""Export the Soundlore concept thesaurus as SKOS: build/soundlore.ttl (Turtle) and build/soundlore.jsonld.

Reads build/concepts.json (run build_concepts.py first). Standard library only.

Model
  - one skos:ConceptScheme for Soundlore;
  - each concept is a skos:Concept with its stable identifier and tree numbers as skos:notation,
    preferred and entry terms, definition, scope note, broader/narrower/related, and its
    Wikidata item as a SKOS mapping (exactMatch, closeMatch, broadMatch, narrowMatch, relatedMatch);
  - each facet is a skos:Collection of its concepts; concepts without a broader term are top concepts;
  - Soundlore-specific data (prompt terms, adherence estimate, definition status) uses the
    vocabulary namespace <base>vocab: .
Concept URIs are <base><identifier>, with <base> taken from scheme.base_uri in concepts.json.
"""
import json, os, re
from collections import OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
B = os.path.join(ROOT, "build")
SKOS = "http://www.w3.org/2004/02/skos/core#"
WD = "http://www.wikidata.org/entity/"
MATCH = {"exact": "exactMatch", "close": "closeMatch", "broad": "broadMatch",
         "narrow": "narrowMatch", "related": "relatedMatch"}


def plain(md):
    """Facet article without Markdown emphasis marks."""
    return re.sub(r"\*([^*]+)\*", r"\1", md)

def lit(s):
    """Turtle string literal."""
    s = str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
    return f'"{s}"'


def main():
    data = json.load(open(os.path.join(B, "concepts.json"), encoding="utf-8"))
    sch, facets, concepts = data["scheme"], data["facets"], data["concepts"]
    base = sch["base_uri"]
    voc = base + "vocab:"
    uid = {c["id"]: c["uid"] for c in concepts}
    scheme_iri = base + "scheme"
    facet_iri = lambda code: f"{base}facet:{code}"

    # ---------- Turtle
    out = [
        f"@prefix skos: <{SKOS}> .",
        "@prefix dcterms: <http://purl.org/dc/terms/> .",
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
        f"@prefix wd: <{WD}> .",
        f"@prefix sl: <{base}> .",
        f"@prefix slv: <{voc}> .",
        "",
        f"<{scheme_iri}> a skos:ConceptScheme ;",
        f"  skos:prefLabel {lit('Soundlore')}@en ;",
        f"  dcterms:title {lit('Soundlore: a thesaurus of musical resources')}@en ;",
        f"  dcterms:hasVersion {lit(sch['version'])} ;",
        "  skos:hasTopConcept " + ", ".join(f"sl:{c['uid']}" for c in concepts if not c["broader"]) + " .",
        "",
    ]
    for f in facets:
        members = [c["uid"] for c in concepts if c["facet"] == f["code"]]
        lines = [f"<{facet_iri(f['code'])}> a skos:Collection",
                 f"skos:prefLabel {lit(f['label'])}@en",
                 f"skos:notation {lit(f['code'])}"]
        if f.get("summary"):
            lines.append(f"skos:definition {lit(f['summary'])}@en")
        if f.get("article"):
            lines.append(f"skos:scopeNote {lit(plain(f['article']))}@en")
        lines.append("skos:member " + ", ".join(f"sl:{m}" for m in members))
        out.append(" ;\n  ".join(lines) + " .\n")
    for c in concepts:
        L = [f"sl:{c['uid']} a skos:Concept",
             f"skos:inScheme <{scheme_iri}>",
             f"skos:prefLabel {lit(c['label'])}@en",
             f"skos:notation {lit(c['uid'])}^^slv:UniqueID"]
        L += [f"skos:notation {lit(t)}^^slv:TreeNumber" for t in c["tree"]]
        if c["synonyms"]:
            L.append("skos:altLabel " + ", ".join(f"{lit(s)}@en" for s in c["synonyms"]))
        if c["definition"]:
            L.append(f"skos:definition {lit(c['definition'])}@en")
        if c["note"]:
            L.append(f"skos:scopeNote {lit(c['note'])}@en")
        if not c["broader"]:
            L.append(f"skos:topConceptOf <{scheme_iri}>")
        for rel in ("broader", "narrower", "related"):
            if c[rel]:
                L.append(f"skos:{rel} " + ", ".join(f"sl:{uid[x]}" for x in c[rel]))
        w = c.get("wikidata")
        if w:
            L.append(f"skos:{MATCH[w['match']]} wd:{w['qid']}")
            if w.get("enwiki_url"):
                L.append(f"rdfs:seeAlso <{w['enwiki_url']}>")
        m = c.get("musicbrainz")
        if m:
            L.append(f"skos:{MATCH[m['match']]} <{m['url']}>")
        if c["prompt_terms"]:
            L.append("slv:promptTerm " + ", ".join(lit(s) for s in c["prompt_terms"]))
        if c["prompt_tags"]:
            L.append("slv:structureTag " + ", ".join(lit(s) for s in c["prompt_tags"]))
        L.append(f"slv:promptAdherenceExpected {lit(c['prompt_adherence_expected'])}")
        if c["definition_status"]:
            L.append(f"slv:definitionStatus {lit(c['definition_status'])}")
        out.append(" ;\n  ".join(L) + " .\n")
    ttl = "\n".join(out)
    open(os.path.join(B, "soundlore.ttl"), "w", encoding="utf-8", newline="\n").write(ttl)

    # ---------- JSON-LD
    ctx = OrderedDict([
        ("skos", SKOS), ("dcterms", "http://purl.org/dc/terms/"), ("rdfs", "http://www.w3.org/2000/01/rdf-schema#"),
        ("wd", WD), ("sl", base), ("slv", voc),
        ("prefLabel", {"@id": "skos:prefLabel", "@language": "en"}),
        ("altLabel", {"@id": "skos:altLabel", "@language": "en", "@container": "@set"}),
        ("definition", {"@id": "skos:definition", "@language": "en"}),
        ("scopeNote", {"@id": "skos:scopeNote", "@language": "en"}),
        ("notation", {"@id": "skos:notation"}),
        ("inScheme", {"@id": "skos:inScheme", "@type": "@id"}),
        ("topConceptOf", {"@id": "skos:topConceptOf", "@type": "@id"}),
        ("hasTopConcept", {"@id": "skos:hasTopConcept", "@type": "@id", "@container": "@set"}),
        ("member", {"@id": "skos:member", "@type": "@id", "@container": "@set"}),
    ])
    for rel in ("broader", "narrower", "related"):
        ctx[rel] = {"@id": f"skos:{rel}", "@type": "@id", "@container": "@set"}
    for m in MATCH.values():
        ctx[m] = {"@id": f"skos:{m}", "@type": "@id"}
    ctx.update(seeAlso={"@id": "rdfs:seeAlso", "@type": "@id"},
               promptTerm={"@id": "slv:promptTerm", "@container": "@set"},
               structureTag={"@id": "slv:structureTag", "@container": "@set"},
               promptAdherenceExpected="slv:promptAdherenceExpected", definitionStatus="slv:definitionStatus")
    graph = [OrderedDict([("@id", scheme_iri), ("@type", "skos:ConceptScheme"), ("prefLabel", "Soundlore"),
                          ("dcterms:title", {"@value": "Soundlore: a thesaurus of musical resources", "@language": "en"}),
                          ("dcterms:hasVersion", sch["version"]),
                          ("hasTopConcept", [f"sl:{c['uid']}" for c in concepts if not c["broader"]])])]
    for f in facets:
        g = OrderedDict([("@id", facet_iri(f["code"])), ("@type", "skos:Collection"), ("prefLabel", f["label"]),
                         ("notation", f["code"])])
        if f.get("summary"):
            g["definition"] = f["summary"]
        if f.get("article"):
            g["scopeNote"] = plain(f["article"])
        g["member"] = [f"sl:{c['uid']}" for c in concepts if c["facet"] == f["code"]]
        graph.append(g)
    for c in concepts:
        g = OrderedDict([("@id", f"sl:{c['uid']}"), ("@type", "skos:Concept"), ("inScheme", scheme_iri),
                         ("prefLabel", c["label"]),
                         ("notation", [{"@value": c["uid"], "@type": "slv:UniqueID"}] +
                                      [{"@value": t, "@type": "slv:TreeNumber"} for t in c["tree"]])])
        if c["synonyms"]: g["altLabel"] = c["synonyms"]
        if c["definition"]: g["definition"] = c["definition"]
        if c["note"]: g["scopeNote"] = c["note"]
        if not c["broader"]: g["topConceptOf"] = scheme_iri
        for rel in ("broader", "narrower", "related"):
            if c[rel]: g[rel] = [f"sl:{uid[x]}" for x in c[rel]]
        w, m = c.get("wikidata"), c.get("musicbrainz")
        targets = ([(w["match"], f"wd:{w['qid']}")] if w else []) + ([(m["match"], m["url"])] if m else [])
        for k, t in targets:
            g.setdefault(MATCH[k], []).append(t)
        for k in MATCH.values():
            if k in g and len(g[k]) == 1: g[k] = g[k][0]
        if w and w.get("enwiki_url"): g["seeAlso"] = w["enwiki_url"]
        if c["prompt_terms"]: g["promptTerm"] = c["prompt_terms"]
        if c["prompt_tags"]: g["structureTag"] = c["prompt_tags"]
        g["promptAdherenceExpected"] = c["prompt_adherence_expected"]
        if c["definition_status"]: g["definitionStatus"] = c["definition_status"]
        graph.append(g)
    json.dump({"@context": ctx, "@graph": graph}, open(os.path.join(B, "soundlore.jsonld"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    n = sum(1 for _ in re.finditer(r"a skos:Concept\b", ttl))
    print(f"SKOS export: {n} concepts, {len(facets)} facet collections -> build/soundlore.ttl, build/soundlore.jsonld")


if __name__ == "__main__":
    main()
