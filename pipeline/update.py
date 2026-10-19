"""Bring the site data up to date with as little work as possible.

1. List JobTech's historical ad files (yearly, and quarterly for the current year).
2. Compare with data/manifest.json. A source file is (re)extracted only when it is
   new, has changed upstream, or its facts were made before vocabulary terms that
   now exist (see extract.py). Everything else reuses stored facts.
3. Facts live as assets on the GitHub release "facts" (--store github), so CI never
   re-reads ad text it has already processed. Locally they stay in data/facts.
4. Re-aggregate data/site when anything changed (or the vocabulary changed).

Usage:
  python3 -I pipeline/update.py                    # local: data/facts on disk
  python3 -I pipeline/update.py --store github     # CI: facts in GitHub release
  python3 -I pipeline/update.py --dry-run          # only report what would happen

Exit code 0; prints "changed=true|false" for CI.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).parent))

INDEX_URL = "https://data.jobtechdev.se/annonser/historiska/index.html"
BASE_URL = "https://data.jobtechdev.se/annonser/historiska/"
MANIFEST = ROOT / "data" / "manifest.json"
RAW = ROOT / "data" / "raw"
FACTS = ROOT / "data" / "facts"
VOCAB = ROOT / "pipeline" / "vocab" / "skills.toml"
TERM_IDS = ROOT / "pipeline" / "vocab" / "term_ids.json"
RELEASE_TAG = "facts"


def sh(*cmd, check=True, capture=False):
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(cmd, check=check, text=True, capture_output=capture)


def list_sources():
    html = urllib.request.urlopen(INDEX_URL, timeout=120).read().decode("utf-8", "replace")
    names = sorted(set(re.findall(r'href="/annonser/historiska/((?:\d{4})(?:-Q[1-4])?\.jsonl\.zip)"', html)))
    years = {n[:4] for n in names if re.fullmatch(r"\d{4}\.jsonl\.zip", n)}
    # Use quarterly files only for years that have no full-year file yet.
    return [n for n in names if re.fullmatch(r"\d{4}\.jsonl\.zip", n) or n[:4] not in years]


def head(name):
    req = urllib.request.Request(BASE_URL + name, method="HEAD")
    with urllib.request.urlopen(req, timeout=120) as r:
        return {"size": int(r.headers.get("Content-Length") or 0), "last_modified": r.headers.get("Last-Modified")}


def stem(name):
    return name.split(".")[0]


def vocab_hash():
    return hashlib.sha256(VOCAB.read_bytes()).hexdigest()[:16]


def current_max_term_id():
    # Make sure every vocabulary term has an id before comparing.
    from extract import load_term_ids
    from vocab import Vocab

    return max(load_term_ids(Vocab()).values())


def download(name):
    RAW.mkdir(parents=True, exist_ok=True)
    dest = RAW / name
    tmp = dest.with_suffix(".part")
    sh("curl", "-fsSL", "--retry", "5", "--retry-delay", "15", "-o", str(tmp), BASE_URL + name)
    os.replace(tmp, dest)
    return dest


def fetch_facts_from_release(stems):
    FACTS.mkdir(parents=True, exist_ok=True)
    have = sh("gh", "release", "view", RELEASE_TAG, "--json", "assets", "-q", ".assets[].name",
              check=False, capture=True)
    if have.returncode != 0:
        return set()
    assets = set(have.stdout.split())
    for s in stems:
        for suffix in (".jsonl.gz", ".meta.json"):
            if s + suffix in assets and not (FACTS / (s + suffix)).exists():
                sh("gh", "release", "download", RELEASE_TAG, "-p", s + suffix, "-D", str(FACTS), "--clobber")
    return assets


def upload_facts(s):
    if sh("gh", "release", "view", RELEASE_TAG, check=False, capture=True).returncode != 0:
        sh("gh", "release", "create", RELEASE_TAG, "--title", "Per-annons-fakta",
           "--notes", "Komprimerade per-annons-fakta från pipeline/extract.py. Används av pipeline/update.py.")
    sh("gh", "release", "upload", RELEASE_TAG, str(FACTS / f"{s}.jsonl.gz"), str(FACTS / f"{s}.meta.json"), "--clobber")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", choices=["local", "github"], default="local")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--keep-raw", action="store_true", help="keep downloaded raw files (default for local)")
    a = ap.parse_args()

    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {"files": {}, "vocab": None}
    sources = list_sources()
    max_tid = current_max_term_id()
    wanted = {}
    for name in sources:
        wanted[name] = head(name)

    todo = []
    for name, info in wanted.items():
        prev = manifest["files"].get(name)
        reason = None
        if not prev:
            reason = "new"
        elif prev.get("size") != info["size"] or prev.get("last_modified") != info["last_modified"]:
            reason = "changed upstream"
        elif prev.get("max_term_id", -1) < max_tid:
            reason = "new vocabulary terms"
        elif a.store == "local" and not (FACTS / f"{stem(name)}.jsonl.gz").exists():
            reason = "facts missing locally"
        if reason:
            todo.append((name, reason))
    dropped = [n for n in manifest["files"] if n not in wanted]
    vocab_changed = manifest.get("vocab") != vocab_hash()

    for name, reason in todo:
        print(f"extract {name}: {reason}")
    for name in dropped:
        print(f"drop {name}: replaced or removed upstream")
    if vocab_changed:
        print("vocabulary changed: re-aggregate")
    changed = bool(todo or dropped or vocab_changed)
    if a.dry_run or not changed:
        print(f"changed={'true' if changed else 'false'}")
        return

    if a.store == "github":
        fetch_facts_from_release([stem(n) for n in wanted])

    for name, reason in todo:
        meta_path = FACTS / f"{stem(name)}.meta.json"
        if reason == "new" and meta_path.exists() and (FACTS / f"{stem(name)}.jsonl.gz").exists():
            meta = json.loads(meta_path.read_text())
            if meta.get("source_size") == wanted[name]["size"] and meta.get("max_term_id", -1) >= max_tid:
                # Facts made earlier on this machine from the same file: adopt them.
                print(f"adopt existing facts for {name}")
                manifest["files"][name] = {**wanted[name], "ads": meta["ads"], "max_term_id": meta["max_term_id"]}
                if a.store == "github":
                    upload_facts(stem(name))
                continue
        raw = RAW / name
        if not raw.exists() or raw.stat().st_size != wanted[name]["size"]:
            raw = download(name)
        sh(sys.executable, "-I", str(ROOT / "pipeline" / "extract.py"), str(raw))
        meta = json.loads((FACTS / f"{stem(name)}.meta.json").read_text())
        manifest["files"][name] = {**wanted[name], "ads": meta["ads"], "max_term_id": meta["max_term_id"]}
        if a.store == "github":
            upload_facts(stem(name))
            if not a.keep_raw:
                raw.unlink(missing_ok=True)
    for name in dropped:
        manifest["files"].pop(name, None)
        for suffix in (".jsonl.gz", ".meta.json"):
            (FACTS / f"{stem(name)}{suffix}").unlink(missing_ok=True)

    # Aggregate only over the files that are current.
    keep = {stem(n) for n in wanted}
    for p in FACTS.glob("*.jsonl.gz"):
        if p.name.split(".")[0] not in keep:
            print(f"ignoring stale facts {p.name}")
            p.rename(p.with_suffix(".stale"))
    sh(sys.executable, "-I", str(ROOT / "pipeline" / "aggregate.py"))
    manifest["vocab"] = vocab_hash()
    MANIFEST.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    print("changed=true")


if __name__ == "__main__":
    main()
