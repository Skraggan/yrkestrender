"""Map old occupation codes that JobTech's taxonomy no longer knows to groups.

Ads from 2006–2016 carry occupation codes from an older AMS taxonomy; some of
them (e.g. many teacher and sales codes) are missing from every taxonomy
version. This learns, from modern ads that have both a headline and an
occupation group, which headline words point to which group, then lets each
unknown code's headlines vote.

Run once; the result (data/legacy_groups.json) is committed and used by
aggregate.py. Needs the raw files for the old years and one modern year.

Usage: python3 -I pipeline/tools/legacy_map.py data/raw/2024.jsonl.zip data/raw/20{06..19}.jsonl.zip
"""
import json
import math
import re
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
from aggregate import Resolver  # noqa: E402

TOKEN = re.compile(r"[a-zåäöéü]{3,}")
STOP = set("""och till för med som söker sökes vi oss nu vår våra din dig hos inom samt eller den det ett
the and for with new heltid deltid tillsvidare vikariat vikarie semestervikarie semestervikariat sommarjobb
extrajobb timanställning ab stockholm göteborg malmö uppsala""".split())


def headline_tokens(h):
    return {t for t in TOKEN.findall((h or "").lower()) if t not in STOP}


def iter_ads(path):
    with zipfile.ZipFile(path) as zf:
        with zf.open(zf.namelist()[0]) as f:
            for line in f:
                yield json.loads(line)


def first(v):
    if isinstance(v, list):
        v = v[0] if v else None
    return v if isinstance(v, dict) else {}


def main(modern, old_files):
    tax = json.loads((ROOT / "data" / "taxonomy.json").read_text(encoding="utf-8"))
    res = Resolver(tax, {})

    # 1. token -> group counts from a modern year
    tg = defaultdict(Counter)
    for ad in iter_ads(modern):
        g = first(ad.get("occupation_group")).get("concept_id")
        if not g:
            continue
        for t in headline_tokens(ad.get("headline")):
            tg[t][g] += 1
    print(f"learned {len(tg):,} headline words", file=sys.stderr)

    # 2. headlines per unmapped legacy code
    by_code = defaultdict(Counter)
    ads_per_code = Counter()
    for path in old_files:
        for ad in iter_ads(path):
            occ = first(ad.get("occupation"))
            legacy = occ.get("legacy_ams_taxonomy_id")
            if not legacy or occ.get("concept_id") or str(legacy) == "0":
                continue
            code = "L" + str(legacy)
            if res.group(code, None):
                continue
            ads_per_code[code] += 1
            by_code[code].update(headline_tokens(ad.get("headline")))
        print(f"read {path}", file=sys.stderr)

    # 3. vote
    out = {}
    for code, toks in by_code.items():
        score = Counter()
        weight = 0.0
        for t, n in toks.items():
            dist = tg.get(t)
            if not dist:
                continue
            total = sum(dist.values())
            if total < 20:
                continue
            # Words that point to few groups count more.
            top = dist.most_common(1)[0][1] / total
            w = n * top
            weight += w
            for g, c in dist.most_common(8):
                score[g] += w * c / total
        if not score:
            continue
        g, s = score.most_common(1)[0]
        conf = s / weight if weight else 0
        if conf >= 0.25:
            out[code[1:]] = {"group": g, "confidence": round(conf, 2), "ads": ads_per_code[code],
                             "label": tax["groups"].get(g, {}).get("label"),
                             "words": [t for t, _ in toks.most_common(6)]}
    mapped = sum(v["ads"] for v in out.values())
    print(f"mapped {len(out)} of {len(by_code)} codes, {mapped:,} of {sum(ads_per_code.values()):,} ads", file=sys.stderr)
    (ROOT / "data" / "legacy_groups.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True),
                                                      encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
