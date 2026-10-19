"""Find words and word pairs that are typical for each occupation group.

Used once while writing the skill vocabulary: prints, for the largest
occupation groups in a sample, the terms whose share of ads is highest
relative to all ads (lift), so the vocabulary covers every line of work.

Usage: python3 -I pipeline/tools/discover_terms.py data/raw/2024.jsonl.zip 200000 > out.txt
"""
import json
import math
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from textnorm import tokens  # noqa: E402

STOP = set("""och att i en ett som är på för med av till du vi har det den de om kan eller
the and to of a in you we for with are our is be on as an will at your this that have work
inom samt vara våra vår ditt din dina ska också hos efter vid alla andra mer mycket både
från under hur över även när där vill vilket men ha har sig sina sitt bli blir får tjänsten
jobbet arbetet arbeta jobb ansökan ansök välkommen""".split())


def main(zip_path, limit):
    df_all = Counter()
    df_group = defaultdict(Counter)
    n_group = Counter()
    labels = {}
    zf = zipfile.ZipFile(zip_path)
    with zf.open(zf.namelist()[0]) as f:
        for i, line in enumerate(f):
            if i >= limit:
                break
            ad = json.loads(line)
            grps = ad.get("occupation_group") or []
            if isinstance(grps, dict):
                grps = [grps]
            if not grps:
                continue
            gid = grps[0]["concept_id"]
            labels[gid] = grps[0]["label"]
            text = (ad.get("headline") or "") + " " + ((ad.get("description") or {}).get("text") or "")
            t = [w for w in tokens(text)]
            grams = {w for w in t if w not in STOP and len(w) > 1 and not w.isdigit()}
            grams |= {a + " " + b for a, b in zip(t, t[1:]) if a not in STOP and b not in STOP}
            n_group[gid] += 1
            df_all.update(grams)
            df_group[gid].update(grams)
    total = sum(n_group.values())
    for gid, n in n_group.most_common(120):
        scored = []
        for term, c in df_group[gid].items():
            if c < max(15, n * 0.03):
                continue
            share = c / n
            lift = share / (df_all[term] / total)
            if lift < 3:
                continue
            scored.append((share * math.log(lift), term, share))
        scored.sort(reverse=True)
        print(f"\n## {labels[gid]} ({n})")
        print(", ".join(f"{t} {s:.0%}" for _, t, s in scored[:45]))


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]))
