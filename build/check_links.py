"""Verify concepts/wikidata.tsv against the Wikidata and English Wikipedia APIs.

For every row it checks that:
  - the Wikidata item exists and is not a redirect;
  - the item is not a disambiguation page or a Wikimedia list article;
  - the item has an English Wikipedia article;
  - that article exists, is not a redirect or a disambiguation page,
    and links back to the same Wikidata item.

It refreshes the `enwiki` title from Wikidata and, for rows that pass, the `checked`
date. Problems are printed and the script exits with status 1 if there are any;
problem rows keep their previous `checked` date.

Usage: python build/check_links.py            check and update the table
       python build/check_links.py --dry-run  check only
Needs network access; standard library only.
"""
import datetime, json, os, sys, time, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TABLE = os.path.join(ROOT, "concepts", "wikidata.tsv")
HEADER = ["uid", "slug", "qid", "match", "enwiki", "checked", "note"]
AGENT = "Soundlore-link-checker/0.6 (music thesaurus build script; Python urllib)"
DISAMBIGUATION, LIST_ARTICLE = "Q4167410", "Q13406463"


def api(base, params, fetch=None):
    params = dict(params, format="json", formatversion="2")
    url = base + "?" + urllib.parse.urlencode(params)
    if fetch:
        return fetch(url)
    req = urllib.request.Request(url, headers={"User-Agent": AGENT})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)


def batches(seq, n=50):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def read_table():
    with open(TABLE, encoding="utf-8") as f:
        lines = f.read().splitlines()
    comments = [ln for ln in lines if ln.startswith("#")]
    body = [ln for ln in lines if ln.strip() and not ln.startswith("#")]
    assert body[0].split("\t") == HEADER, f"unexpected header in {TABLE}"
    rows = [dict(zip(HEADER, (ln.split("\t") + [""] * len(HEADER))[:len(HEADER)])) for ln in body[1:]]
    return comments, rows


def write_table(comments, rows):
    with open(TABLE, "w", encoding="utf-8", newline="") as f:
        for c in comments:
            f.write(c + "\n")
        f.write("\t".join(HEADER) + "\n")
        for r in rows:
            f.write("\t".join(r[k] for k in HEADER) + "\n")


def check(rows, fetch=None):
    """Return {qid: problem text or None} and {qid: enwiki title}."""
    qids = sorted({r["qid"] for r in rows})
    items = {}
    for b in batches(qids):
        data = api("https://www.wikidata.org/w/api.php", {
            "action": "wbgetentities", "ids": "|".join(b), "props": "info|sitelinks|claims",
            "sitefilter": "enwiki"}, fetch)
        if "error" in data:
            raise RuntimeError(data["error"])
        items.update(data.get("entities", {}))
    problems, titles = {}, {}
    for q in qids:
        e = items.get(q)
        if not e or "missing" in e:
            problems[q] = "Wikidata item does not exist"; continue
        if e.get("id") != q or "redirects" in e:
            problems[q] = f"Wikidata item redirects to {e.get('id')}"; continue
        p31 = {c["mainsnak"].get("datavalue", {}).get("value", {}).get("id")
               for c in e.get("claims", {}).get("P31", [])}
        if DISAMBIGUATION in p31:
            problems[q] = "Wikidata item is a disambiguation page"; continue
        title = e.get("sitelinks", {}).get("enwiki", {}).get("title")
        if not title:
            problems[q] = "no English Wikipedia article"; continue
        titles[q] = title
        if LIST_ARTICLE in p31:
            problems[q] = "Wikipedia article is a list article"
    pages = {}
    for b in batches(sorted(set(titles.values()))):
        data = api("https://en.wikipedia.org/w/api.php", {
            "action": "query", "prop": "pageprops", "ppprop": "disambiguation|wikibase_item",
            "titles": "|".join(b)}, fetch)
        q = data.get("query", {})
        norm = {n["from"]: n["to"] for n in q.get("normalized", [])}
        redirected = {n["from"]: n["to"] for n in q.get("redirects", [])}
        byname = {p["title"]: p for p in q.get("pages", [])}
        for t in b:
            t2 = norm.get(t, t)
            pages[t] = (byname.get(t2), redirected.get(t2))
    for q, t in titles.items():
        page, redirect = pages.get(t, (None, None))
        if redirect:
            problems[q] = f"Wikipedia article '{t}' redirects to '{redirect}'"
        elif not page or page.get("missing"):
            problems[q] = f"Wikipedia article '{t}' does not exist"
        elif "disambiguation" in page.get("pageprops", {}):
            problems[q] = f"Wikipedia article '{t}' is a disambiguation page"
        elif page.get("pageprops", {}).get("wikibase_item") != q:
            problems[q] = f"Wikipedia article '{t}' belongs to {page.get('pageprops', {}).get('wikibase_item')}"
    return problems, titles


def main(argv):
    dry = "--dry-run" in argv
    comments, rows = read_table()
    problems, titles = check(rows)
    today = datetime.date.today().isoformat()
    n_bad = 0
    for r in rows:
        q = r["qid"]
        if q in titles:
            r["enwiki"] = titles[q]
        p = problems.get(q)
        if p:
            # a list article may be an accepted, documented 'related' match
            if p.endswith("list article") and r["match"] == "related" and "list article" in r["note"]:
                r["checked"] = today; continue
            n_bad += 1
            print(f"{r['uid']}  {r['slug']:28} {q:12} {p}")
        else:
            r["checked"] = today
    print(f"{len(rows)} links checked, {len(rows) - n_bad} ok, {n_bad} with problems")
    if not dry:
        write_table(comments, rows)
    return 1 if n_bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
