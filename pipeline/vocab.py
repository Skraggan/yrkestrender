"""Load the skill vocabulary (vocab/skills.toml) into lookup tables."""
import re
import tomllib
import unicodedata
from pathlib import Path

from textnorm import term_tokens

VOCAB_PATH = Path(__file__).parent / "vocab" / "skills.toml"

# Swedish endings added to terms written with a trailing "*".
_SUFFIXES = ["", "en", "et", "n", "t", "er", "ar", "or", "na", "erna", "arna", "orna", "ens", "ets", "s"]


def slugify(name):
    s = name.lower().replace("+", "plus").replace("#", "sharp").replace(".net", "dotnet")
    s = s.replace("å", "a").replace("ä", "a").replace("ö", "o")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def expand(term):
    star = term.endswith("*")
    toks = term_tokens(term.rstrip("*"))
    if not toks:
        return []
    if not star:
        return [toks]
    head, last = toks[:-1], toks[-1]
    return [head + (last + suf,) for suf in _SUFFIXES]


class Vocab:
    """Terms are numbered in file order; the id of a term never depends on skills.

    term_ids: canonical term string -> id (stable as long as terms are only appended)
    grams[n]: n-gram (space-joined tokens) -> term id, for n = 1..4
    """

    def __init__(self, path=VOCAB_PATH):
        cfg = tomllib.loads(path.read_text(encoding="utf-8"))
        self.kinds = [{"id": k, "name": v} for k, v in cfg.get("kinds", {"kompetens": "Kompetenser"}).items()]
        kind_ids = {k["id"] for k in self.kinds}
        self.categories = []   # [{id, name, kind}]
        self.skills = []       # [{id, name, category, terms: [term strings]}]
        self.term_skill = {}   # term string -> skill id
        self.grams = {1: {}, 2: {}, 3: {}, 4: {}}
        errors = []
        for cat_id, cat in cfg["categories"].items():
            kind = cat.get("kind", "kompetens")
            if kind not in kind_ids:
                errors.append(f"category {cat_id} has unknown kind {kind}")
            self.categories.append({"id": cat_id, "name": cat["name"], "kind": kind})
            for name, terms in cat["skills"].items():
                sid = slugify(name)
                if any(s["id"] == sid for s in self.skills):
                    errors.append(f"duplicate skill id {sid}")
                self.skills.append({"id": sid, "name": name, "category": cat_id, "kind": kind, "terms": terms})
                for term in terms:
                    if term in self.term_skill:
                        errors.append(f"term '{term}' in both {self.term_skill[term]} and {sid}")
                    self.term_skill[term] = sid
                    for toks in expand(term):
                        if len(toks) > 4:
                            errors.append(f"term '{term}' has more than 4 words")
                            continue
                        gram = " ".join(toks)
                        prev = self.grams[len(toks)].get(gram)
                        if prev is not None and prev != term:
                            # Same surface form from two terms (e.g. an inflection): keep the first.
                            continue
                        self.grams[len(toks)][gram] = term
        if errors:
            raise ValueError("vocabulary errors:\n  " + "\n  ".join(errors))
        self.skill_by_id = {s["id"]: s for s in self.skills}


def match_terms(toks, grams):
    """Return the set of vocabulary terms present in a token list."""
    found = set()
    g1, g2, g3 = grams[1], grams[2], grams[3]
    for t in set(toks) & g1.keys():
        found.add(g1[t])
    if len(toks) > 1:
        for bg in set(map(" ".join, zip(toks, toks[1:]))) & g2.keys():
            found.add(g2[bg])
    if len(toks) > 2 and g3:
        for tg in set(map(" ".join, zip(toks, toks[1:], toks[2:]))) & g3.keys():
            found.add(g3[tg])
    g4 = grams[4]
    if len(toks) > 3 and g4:
        for qg in set(map(" ".join, zip(toks, toks[1:], toks[2:], toks[3:]))) & g4.keys():
            found.add(g4[qg])
    return found
