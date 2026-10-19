"""Read raw yearly/quarterly ad files once and write compact per-ad facts.

This is the only step that reads the 10+ GB of ad text. Each ad becomes one
small JSON array in data/facts/<file>.jsonl.gz holding what the site needs:
date, occupation, location, employer, a few conditions and the ids of every
vocabulary term found in the text. Everything after this (counting per year,
occupation, region, skill...) runs on the facts in minutes.

Term ids come from pipeline/vocab/term_ids.json, which is append-only: moving a
term to another skill, renaming or merging skills needs no re-extraction. Only
brand-new terms do, and update.py re-extracts exactly the files whose facts
were made before those terms existed.

Usage: python3 -I pipeline/extract.py data/raw/2024.jsonl.zip [more files...] [--workers N]
"""
import argparse
import gzip
import hashlib
import json
import os
import sys
import time
import zipfile
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from textnorm import tokens  # noqa: E402
from vocab import Vocab, match_terms  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FACTS_DIR = ROOT / "data" / "facts"
TERM_IDS = Path(__file__).parent / "vocab" / "term_ids.json"
FACTS_VERSION = 1

# Fact columns, in order. Kept as arrays to keep files small.
COLUMNS = ["key", "date", "occupation", "group", "municipality", "postcode", "city",
           "orgnr", "employer", "hours", "duration", "experience", "language", "vacancies", "source", "terms"]


def load_term_ids(vocab):
    ids = json.loads(TERM_IDS.read_text(encoding="utf-8")) if TERM_IDS.exists() else {}
    next_id = max(ids.values(), default=-1) + 1
    for term in vocab.term_skill:
        if term not in ids:
            ids[term] = next_id
            next_id += 1
    TERM_IDS.write_text(json.dumps(ids, ensure_ascii=False, indent=0), encoding="utf-8")
    return ids


def first(v):
    if isinstance(v, list):
        v = v[0] if v else None
    return v if isinstance(v, dict) else None


def s(v):
    """String or None, whatever type the source used."""
    if v is None or v == "":
        return None
    return str(v).strip() or None


def iter_raw(path):
    path = Path(path)
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as zf:
            for name in zf.namelist():
                if name.endswith((".jsonl", ".json")):
                    with zf.open(name) as f:
                        yield from f
    elif path.suffix == ".zst":
        raise SystemExit("zst files are not supported; use the .zip variant")
    else:
        with open(path, "rb") as f:
            yield from f


def fact(ad, grams, term_id):
    desc = ad.get("description") if isinstance(ad.get("description"), dict) else {}
    headline = s(ad.get("headline")) or ""
    text = headline + " \n " + (s(desc.get("text")) or "")
    occ = first(ad.get("occupation")) or {}
    grp = first(ad.get("occupation_group")) or {}
    addr = ad.get("workplace_address") if isinstance(ad.get("workplace_address"), dict) else {}
    emp = ad.get("employer") if isinstance(ad.get("employer"), dict) else {}
    date = (s(ad.get("publication_date")) or "")[:10]

    key = str(ad.get("id") or "")[:16]
    if not key:
        h = hashlib.sha1(f"{date}|{headline}|{emp.get('name')}|{text[:300]}".encode("utf-8", "replace"))
        key = "h" + h.hexdigest()[:15]

    legacy = s(occ.get("legacy_ams_taxonomy_id"))
    occ_id = s(occ.get("concept_id")) or (("L" + legacy) if legacy else None)
    muni = s(addr.get("municipality_code"))
    postcode = (s(addr.get("postcode")) or "").replace(" ", "")[:5] or None
    city = (s(addr.get("city")) or s(addr.get("municipality")) or "")[:40] or None
    hours = (s((first(ad.get("working_hours_type")) or {}).get("label")) or "")[:1] or None   # H(eltid) / D(eltid)
    duration = s((first(ad.get("duration")) or {}).get("label"))
    exp = ad.get("experience_required")
    vac = ad.get("number_of_vacancies")
    try:
        vac = int(vac) if vac not in (None, "") else None
    except (TypeError, ValueError):
        vac = None

    terms = sorted(term_id[t] for t in match_terms(tokens(text), grams))
    return [key, date, occ_id, s(grp.get("concept_id")), muni, postcode, city,
            s(emp.get("organization_number")), (s(emp.get("name")) or "")[:80] or None,
            hours, duration, None if exp is None else int(bool(exp)),
            s(ad.get("detected_language")), vac, s(ad.get("source_type")), terms]


def extract_file(args):
    raw_path, term_id = args
    raw_path = Path(raw_path)
    vocab = Vocab()
    name = raw_path.name.split(".")[0]
    out_path = FACTS_DIR / f"{name}.jsonl.gz"
    tmp = out_path.with_suffix(".tmp")
    t0 = time.time()
    n = bad = 0
    with gzip.open(tmp, "wt", encoding="utf-8", compresslevel=6) as out:
        for line in iter_raw(raw_path):
            line = line.strip()
            if not line:
                continue
            try:
                ad = json.loads(line)
            except json.JSONDecodeError:
                bad += 1
                continue
            out.write(json.dumps(fact(ad, vocab.grams, term_id), ensure_ascii=False, separators=(",", ":")))
            out.write("\n")
            n += 1
    os.replace(tmp, out_path)
    st = raw_path.stat()
    meta = {"source": raw_path.name, "source_size": st.st_size, "ads": n, "bad_lines": bad,
            "max_term_id": max(term_id.values()), "facts_version": FACTS_VERSION, "columns": COLUMNS,
            "seconds": round(time.time() - t0)}
    (FACTS_DIR / f"{name}.meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return f"{raw_path.name}: {n:,} ads in {meta['seconds']}s"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    a = ap.parse_args()
    FACTS_DIR.mkdir(parents=True, exist_ok=True)
    term_id = load_term_ids(Vocab())
    # Largest files first so the pool finishes evenly.
    files = sorted(a.files, key=lambda p: -Path(p).stat().st_size)
    with Pool(min(a.workers, len(files))) as pool:
        for msg in pool.imap_unordered(extract_file, [(f, term_id) for f in files]):
            print(msg, flush=True)


if __name__ == "__main__":
    main()
