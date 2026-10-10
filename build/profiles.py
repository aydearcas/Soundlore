"""Read genres/profiles_*.txt, resolve inheritance (@genre) and validate concepts and names.

Syntax:
  genre = C ... | F ... | O ...   characteristic / frequent / occasional resources
  @other genre                    inherit that genre's profile
  genre += ...                    add resources to an existing profile
  genre = NONMUSICAL              mark an entry that is not music
"""
import json, glob, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = {"C": 3, "F": 2, "O": 1}
NONMUSICAL = set()

def load_raw():
    raw = {}
    for f in sorted(glob.glob(os.path.join(ROOT, "genres", "profiles_*.txt"))):
        for ln, line in enumerate(open(f, encoding="utf-8"), 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            add = " += " in line
            name, rhs = line.split(" += " if add else " = ", 1)
            name = name.strip()
            if rhs.strip() == "NONMUSICAL":
                NONMUSICAL.add(name); continue
            entries = []  # (level, text)
            for part in rhs.split("|"):
                part = part.strip()
                if not part:
                    continue
                lvl, *toks = part.split()
                assert lvl in W, f"{f}:{ln} unknown level {lvl}"
                entries.append((lvl, " ".join(toks)))
            if add:
                assert name in raw, f"{f}:{ln} '+=' on a profile that does not exist: {name}"
                raw[name] = (raw[name][0] + entries, raw[name][1])
                continue
            if name in raw:
                print(f"WARNING: duplicate profile {name}")
            raw[name] = (entries, f"{os.path.basename(f)}:{ln}")
    return raw

def tokenize(text, concept_ids, genre_names):
    """Split concepts and @genre references (genre names may contain spaces: longest match wins)."""
    out, i, words = [], 0, text.split()
    while i < len(words):
        w = words[i]
        if w.startswith("@"):
            best = None
            for j in range(len(words), i, -1):
                cand = " ".join(words[i:j])[1:]
                if cand in genre_names:
                    best = (cand, j); break
            if best:
                out.append(("@", best[0])); i = best[1]; continue
            out.append(("?@", w[1:])); i += 1; continue
        out.append(("c" if w in concept_ids else "?", w)); i += 1
    return out

def resolve(concept_ids):
    raw = load_raw()
    names = set(raw)
    parsed, errors = {}, []
    for g, (entries, src) in raw.items():
        items = []
        for lvl, text in entries:
            for kind, tok in tokenize(text, concept_ids, names):
                if kind == "?":
                    errors.append(f"{src} [{g}] unknown concept: {tok}")
                elif kind == "?@":
                    errors.append(f"{src} [{g}] unknown inherited genre: @{tok}")
                else:
                    items.append((kind, tok, W[lvl]))
        parsed[g] = items
    cache = {}
    def prof(g, stack=()):
        if g in cache:
            return cache[g]
        if g in stack:
            errors.append(f"circular inheritance: {' > '.join(stack + (g,))}"); return {}
        p = {}
        # A profile with characteristic resources of its own inherits one level down (C→F, F→O);
        # a pure variant (no own C) inherits unchanged.
        own_c = any(kind == "c" and w == 3 for kind, tok, w in parsed[g])
        for kind, tok, w in parsed[g]:
            if kind == "@":
                for c, wc in prof(tok, stack + (g,)).items():
                    wi = max(1, wc - 1) if own_c else wc
                    p[c] = max(p.get(c, 0), wi)
        for kind, tok, w in parsed[g]:
            if kind == "c":
                p[tok] = w  # explicit level wins
        cache[g] = p
        return p
    return {g: prof(g) for g in parsed}, errors

if __name__ == "__main__":
    C = json.load(open(os.path.join(ROOT, "build", "concepts.json"), encoding="utf-8"))
    profiles, errors = resolve({c["id"] for c in C["concepts"]})
    for e in errors: print(e)
    print(f"profiles: {len(profiles)} | non-musical: {len(NONMUSICAL)} | errors: {len(errors)}")
