"""Turn per-ad facts (data/facts) into the JSON the website is built from (data/site).

Runs in a few minutes on all years. Nothing here reads raw ad text, so the
skill list can be regrouped and the site's numbers changed freely.

Usage: python3 -I pipeline/aggregate.py [--facts data/facts] [--out data/site]
"""
import argparse
import gzip
import json
import math
import os
import shutil
import sys
from collections import Counter, defaultdict
from datetime import date
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from vocab import Vocab, slugify  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TAXONOMY = ROOT / "data" / "taxonomy.json"
LEGACY_GROUPS = ROOT / "data" / "legacy_groups.json"   # learned by tools/legacy_map.py
TERM_IDS = Path(__file__).parent / "vocab" / "term_ids.json"

# Fact column positions (see extract.COLUMNS).
K, D, OCC, GRP, MUNI, POST, CITY, ORG, EMP, HOURS, DUR, EXP, LANG, VAC, SRC, TERMS = range(16)

MIN_GROUP_ADS_FOR_SHARE = 40     # yearly share is shown only when the group had this many ads that year
MIN_SKILL_ADS = 8                # a skill is listed for an occupation when mentioned in this many ads (last 12 m)
COOC_MONTHS = 24                 # window for "nämns ofta tillsammans med"


# --------------------------------------------------------------------------- helpers

def ym_index(ym):
    return int(ym[:4]) * 12 + int(ym[5:7]) - 1


def ym_str(i):
    return f"{i // 12:04d}-{i % 12 + 1:02d}"


def r4(x):
    return round(x, 4)


_KEEP_UPPER = {"AB", "HB", "KB", "AS", "ASA", "A/S", "AB:S", "IT", "HVB", "LSS", "BRF", "ICA", "SCA", "SKF", "ABB", "SAAB", "SJ", "SL", "SVT", "SR", "UR", "KTH", "LTU", "SLU", "KI", "VD", "HR", "BMW", "IKEA", "H&M"}


def tidy_name(name):
    """'REGION SKÅNE' -> 'Region Skåne'; leaves mixed-case names alone."""
    if not name or not name.isupper():
        return name
    words = []
    for w in name.split():
        words.append(w if w in _KEEP_UPPER else w.capitalize())
    return " ".join(words)


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))


# --------------------------------------------------------------------------- resolution

class Resolver:
    """Maps the raw occupation/location values in facts to groups and regions."""

    def __init__(self, tax, postcode_muni):
        self.tax = tax
        self.postcode_muni = postcode_muni
        self.city_muni = {m["label"].lower(): code for code, m in tax["municipalities"].items()}
        self.city_muni.update({"göteborg": "1480", "gothenburg": "1480", "stockholm": "0180", "malmö": "1280",
                               "gotland": "0980", "visby": "0980"})
        self._occ_cache = {}
        self.legacy_groups = {}
        if LEGACY_GROUPS.exists():
            self.legacy_groups = {k: v["group"] for k, v in json.loads(LEGACY_GROUPS.read_text(encoding="utf-8")).items()}

    def group(self, occ, grp):
        if grp and grp in self.tax["groups"]:
            return self._active_group(grp)
        if not occ:
            return None
        if occ in self._occ_cache:
            return self._occ_cache[occ]
        cid = occ
        if occ.startswith("L"):
            cid = self.tax["legacy_occupations"].get(occ[1:])
        g = None
        if cid and cid in self.tax["occupations"]:
            g = self.tax["occupations"][cid]["group"]
            g = self._active_group(g) if g else None
        elif occ.startswith("L") and occ[1:] in self.legacy_groups:
            g = self._active_group(self.legacy_groups[occ[1:]])
        self._occ_cache[occ] = g
        return g

    def _active_group(self, g):
        info = self.tax["groups"].get(g)
        if info and info["deprecated"] and info["replaced_by"]:
            return info["replaced_by"][0]
        return g

    def municipality(self, muni, postcode, city):
        if muni and muni in self.tax["municipalities"]:
            return muni
        if postcode:
            m = self.postcode_muni.get(postcode) or self.postcode_muni.get(postcode[:3])
            if m:
                return m
        if city:
            return self.city_muni.get(city.lower())
        return None


# --------------------------------------------------------------------------- pass 1: keys + postcodes

def scan_file(path):
    """Collect boundary keys (for dedupe across files) and postcode -> municipality pairs."""
    stem = path.name.split(".")[0]
    file_year = stem[:4]
    keys = {}
    pc = Counter()
    last = ""
    today = date.today().isoformat()
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            d = row[D]
            if last < d <= today:
                last = d
            if d[:4] != file_year or d[5:7] in ("01", "12"):
                keys[row[K]] = d
            if row[MUNI] and row[POST]:
                pc[(row[POST], row[MUNI])] += 1
    return stem, keys, pc, last


def build_postcode_map(pc_counts):
    best5, by3 = {}, defaultdict(Counter)
    agg = defaultdict(Counter)
    for (post, muni), c in pc_counts.items():
        agg[post][muni] += c
        by3[post[:3]][muni] += c
    for post, c in agg.items():
        best5[post] = c.most_common(1)[0][0]
    for p3, c in by3.items():
        muni, n = c.most_common(1)[0]
        if n / sum(c.values()) >= 0.6:   # only when a 3-digit prefix is clearly one municipality
            best5[p3] = muni
    return best5


# --------------------------------------------------------------------------- pass 2: counting

def count_file(args):
    path, skip_keys, tax, postcode_muni, term_skill_idx, n_skills, last_ym, cooc_from = args
    res = Resolver(tax, postcode_muni)
    region_of_muni = {code: m["region"] for code, m in tax["municipalities"].items()}
    gidx = {}
    out = {
        "groups": [],
        "tot": Counter(),        # (ym, g)
        "skill": Counter(),      # (ym, g, s) packed int
        "reg": Counter(),        # (year, g, region)
        "reg_skill": Counter(),  # (year, region, s)
        "reg_ym": Counter(),     # (ym, region)
        "cond": Counter(),       # (year, g, cond)
        "names": Counter(),      # (g, occ) last 36 months
        "emp": Counter(),        # (g, employer) last 36 months
        "emp_names": {},
        "cooc": Counter(),       # (s1, s2) packed, national, last COOC_MONTHS
        "cooc_n": Counter(),     # s -> ads in cooc window
        "cooc_ads": 0,
        "dupes": 0, "ads": 0, "no_group": 0, "no_region": 0,
    }
    emp_from = last_ym - 35
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            if row[K] in skip_keys:
                out["dupes"] += 1
                continue
            d = row[D]
            if len(d) < 7:
                continue
            if d < "2006-01-01":
                continue
            ym = ym_index(d[:7])
            if ym > last_ym:
                continue
            year = int(d[:4])
            g = res.group(row[OCC], row[GRP])
            if g is None:
                out["no_group"] += 1
                g = "_none"
            gi = gidx.get(g)
            if gi is None:
                gi = gidx[g] = len(out["groups"])
                out["groups"].append(g)
            muni = res.municipality(row[MUNI], row[POST], row[CITY])
            region = region_of_muni.get(muni) if muni else None
            if region is None:
                out["no_region"] += 1
                region = "00"
            out["ads"] += 1
            out["tot"][(ym, gi)] += 1
            out["reg"][(year, gi, region)] += 1
            out["reg_ym"][(ym, region)] += 1

            skills = {term_skill_idx[t] for t in row[TERMS] if t in term_skill_idx}
            base = (ym * 1024 + gi) * 1024
            for s in skills:
                out["skill"][base + s] += 1
                out["reg_skill"][(year, region, s)] += 1

            if row[HOURS]:
                out["cond"][(year, gi, "hours_" + row[HOURS])] += 1
            if row[DUR]:
                out["cond"][(year, gi, "perm" if row[DUR].lower().startswith("till") else "temp")] += 1
            if row[EXP] is not None:
                out["cond"][(year, gi, "exp_" + str(row[EXP]))] += 1
            if row[LANG]:
                out["cond"][(year, gi, "lang_en" if row[LANG] == "en" else "lang_other")] += 1

            if ym >= emp_from:
                if row[OCC] and not row[OCC].startswith("L"):
                    out["names"][(gi, row[OCC])] += 1
                ek = row[ORG] or (("n:" + row[EMP].lower()) if row[EMP] else None)
                if ek:
                    out["emp"][(gi, ek)] += 1
                    if row[EMP] and ek not in out["emp_names"]:
                        out["emp_names"][ek] = row[EMP]
            if ym >= cooc_from and skills:
                out["cooc_ads"] += 1
                sl = sorted(skills)
                for s in sl:
                    out["cooc_n"][s] += 1
                for i, a in enumerate(sl):
                    for b in sl[i + 1:]:
                        out["cooc"][a * n_skills + b] += 1
    return out


# --------------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--facts", default=str(ROOT / "data" / "facts"))
    ap.add_argument("--out", default=str(ROOT / "data" / "site"))
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    a = ap.parse_args()

    facts = sorted(Path(a.facts).glob("*.jsonl.gz"))
    if not facts:
        raise SystemExit("no facts found; run extract.py first")
    tax = json.loads(TAXONOMY.read_text(encoding="utf-8"))
    vocab = Vocab()
    term_ids = json.loads(TERM_IDS.read_text(encoding="utf-8"))
    skill_list = vocab.skills
    sidx = {s["id"]: i for i, s in enumerate(skill_list)}
    term_skill_idx = {tid: sidx[vocab.term_skill[term]] for term, tid in term_ids.items() if term in vocab.term_skill}
    n_skills = len(skill_list)

    # Pass 1: dedupe boundary ads across files, learn postcodes, find the data's last month.
    print("pass 1: scanning keys", flush=True)
    with Pool(min(a.workers, len(facts))) as pool:
        scans = pool.map(scan_file, facts)
    owner = {}
    skip = defaultdict(set)
    for stem, keys, _, _ in scans:
        for k, d in keys.items():
            if k not in owner:
                owner[k] = (stem, d)
                continue
            prev_stem, _ = owner[k]
            # Keep the copy in the file whose year matches the publication year.
            if stem[:4] == d[:4] and prev_stem[:4] != d[:4]:
                skip[prev_stem].add(k)
                owner[k] = (stem, d)
            else:
                skip[stem].add(k)
    pc = Counter()
    for _, _, c, _ in scans:
        pc.update(c)
    postcode_muni = build_postcode_map(pc)
    metas = [json.loads((p.parent / (p.name.split(".")[0] + ".meta.json")).read_text()) for p in facts]
    last_day = max(last for *_, last in scans)
    last_ym = ym_index(last_day[:7])
    # A month counts as complete only if the data reaches its last days.
    if int(last_day[8:10]) < 25:
        last_ym -= 1
    cooc_from = last_ym - COOC_MONTHS + 1
    print(f"  dupes skipped: {sum(len(s) for s in skip.values()):,}; last month {ym_str(last_ym)}", flush=True)

    # Pass 2: count.
    print("pass 2: counting", flush=True)
    jobs = [(p, skip.get(p.name.split(".")[0], set()), tax, postcode_muni, term_skill_idx, n_skills, last_ym, cooc_from)
            for p in sorted(facts, key=lambda p: -p.stat().st_size)]
    groups = []
    gmap = {}
    tot = Counter(); skill = Counter(); reg = Counter(); reg_skill = Counter(); reg_ym = Counter()
    cond = Counter(); names = Counter(); emp = Counter(); emp_names = {}
    cooc = Counter(); cooc_n = Counter(); cooc_ads = 0
    stats = Counter()
    with Pool(min(a.workers, len(jobs))) as pool:
        for part in pool.imap_unordered(count_file, jobs):
            remap = []
            for g in part["groups"]:
                if g not in gmap:
                    gmap[g] = len(groups)
                    groups.append(g)
                remap.append(g)   # counters below are keyed by group concept id
            for (ym, gi), c in part["tot"].items():
                tot[(ym, remap[gi])] += c
            for packed, c in part["skill"].items():
                s = packed % 1024
                gi = (packed // 1024) % 1024
                ym = packed // (1024 * 1024)
                skill[(ym, remap[gi], s)] += c
            for (y, gi, r), c in part["reg"].items():
                reg[(y, remap[gi], r)] += c
            reg_skill.update(part["reg_skill"])
            reg_ym.update(part["reg_ym"])
            for (y, gi, k), c in part["cond"].items():
                cond[(y, remap[gi], k)] += c
            for (gi, o), c in part["names"].items():
                names[(remap[gi], o)] += c
            for (gi, e), c in part["emp"].items():
                emp[(remap[gi], e)] += c
            for k, v in part["emp_names"].items():
                emp_names.setdefault(k, v)
            cooc.update(part["cooc"]); cooc_n.update(part["cooc_n"]); cooc_ads += part["cooc_ads"]
            for k in ("dupes", "ads", "no_group", "no_region"):
                stats[k] += part[k]
            print(f"  merged part: {part['ads']:,} ads", flush=True)
    print(f"  {dict(stats)}", flush=True)

    build_site(Path(a.out), tax, vocab, skill_list, groups, tot, skill, reg, reg_skill, reg_ym, cond, names, emp,
               emp_names, cooc, cooc_n, cooc_ads, n_skills, last_ym, stats, metas)


# --------------------------------------------------------------------------- site JSON

def build_site(out, tax, vocab, skill_list, groups, tot, skill, reg, reg_skill, reg_ym, cond, names, emp, emp_names,
               cooc, cooc_n, cooc_ads, n_skills, last_ym, stats, metas):
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    first_ym = min(ym for ym, _ in tot)
    years = list(range(first_ym // 12, last_ym // 12 + 1))
    L12 = range(last_ym - 11, last_ym + 1)
    P12 = range(last_ym - 23, last_ym - 11)
    B12 = range(last_ym - 47, last_ym - 35)   # same 12 months three years earlier
    last_year = last_ym // 12
    partial_last_year = (last_ym % 12) != 11

    # Occupation-level series start in the first year where nearly all ads have an occupation
    # (2006–2007 ads in the source mostly lack occupation codes).
    none_year, all_year = Counter(), Counter()
    for (ym, g), c in tot.items():
        all_year[ym // 12] += c
        if g == "_none":
            none_year[ym // 12] += c
    occ_first_year = next((y for y in years if all_year[y] and none_year[y] / all_year[y] < 0.15), years[0])
    occ_years = [y for y in years if y >= occ_first_year]
    occ_first_ym = occ_first_year * 12

    # Index structures.
    g_tot_ym = defaultdict(Counter)            # g -> ym -> ads
    for (ym, g), c in tot.items():
        g_tot_ym[g][ym] += c
    nat_ym = Counter()
    for (ym, g), c in tot.items():
        nat_ym[ym] += c
    g_skill_ym = defaultdict(lambda: defaultdict(Counter))  # g -> s -> ym -> ads
    s_ym = defaultdict(Counter)                              # s -> ym -> ads (national)
    for (ym, g, s), c in skill.items():
        g_skill_ym[g][s][ym] += c
        s_ym[s][ym] += c

    def wsum(counter, window):
        return sum(counter.get(i, 0) for i in window)

    def yearly(counter):
        y = Counter()
        for ym, c in counter.items():
            y[ym // 12] += c
        return y

    nat_year = yearly(nat_ym)
    nat_L12, nat_B12 = wsum(nat_ym, L12), wsum(nat_ym, B12)

    group_slug = {}
    used = set()
    for g in groups:
        if g == "_none":
            continue
        label = tax["groups"].get(g, {}).get("label", g)
        slug = slugify(label)[:80]
        while slug in used:
            slug += "-2"
        used.add(slug)
        group_slug[g] = slug
    region_label = dict(tax["regions"])
    region_slug = {code: slugify(lbl.replace(" län", "")) for code, lbl in region_label.items()}
    skill_meta = [{"id": s["id"], "name": s["name"], "category": s["category"], "kind": s["kind"]} for s in skill_list]

    recent_years = {last_year} | ({last_year - 1} if partial_last_year else set())
    reg_recent_by_g = defaultdict(Counter)
    region_total = Counter()
    for (y, g, r), c in reg.items():
        if r != "00" and y in recent_years:
            reg_recent_by_g[g][r] += c
            region_total[r] += c
    names_by_g = defaultdict(dict)
    for (g, o), c in names.items():
        names_by_g[g][o] = c
    emp_by_g = defaultdict(dict)
    for (g, e), c in emp.items():
        emp_by_g[g][e] = c
    reg_year_tot = Counter()
    for (ym, r), c in reg_ym.items():
        reg_year_tot[(ym // 12, r)] += c

    # ---- occupation pages
    occ_index = []
    profiles = {}
    for g, slug in group_slug.items():
        gi = tax["groups"].get(g, {})
        ym_counts = g_tot_ym[g]
        ads_L12, ads_P12, ads_B12 = wsum(ym_counts, L12), wsum(ym_counts, P12), wsum(ym_counts, B12)
        g_year = yearly(ym_counts)
        if sum(ym_counts.values()) < 50:
            continue
        skills_out = []
        prof = {}
        for s, sc in g_skill_ym[g].items():
            c_L12 = wsum(sc, L12)
            c_B12 = wsum(sc, B12)
            sh_L12 = c_L12 / ads_L12 if ads_L12 else None
            sh_B12 = c_B12 / ads_B12 if ads_B12 >= MIN_GROUP_ADS_FOR_SHARE else None
            sy = yearly(sc)
            by_year = {str(y): r4(sy.get(y, 0) / g_year[y]) for y in occ_years if g_year.get(y, 0) >= MIN_GROUP_ADS_FOR_SHARE}
            if sh_L12 is not None:
                prof[s] = sh_L12
            if c_L12 >= MIN_SKILL_ADS or (c_B12 >= MIN_SKILL_ADS and ads_L12 >= MIN_GROUP_ADS_FOR_SHARE):
                skills_out.append({
                    "s": skill_list[s]["id"], "n": c_L12,
                    "sh": r4(sh_L12) if sh_L12 is not None else None,
                    "sh3": r4(sh_B12) if sh_B12 is not None else None,
                    "y": by_year,
                })
        skills_out.sort(key=lambda x: -(x["sh"] or 0))
        profiles[g] = prof

        reg_counts = reg_recent_by_g.get(g, Counter())
        g_reg_total = sum(reg_counts.values())
        all_reg_total = sum(region_total.values())
        regions_out = []
        for r, c in reg_counts.most_common():
            lq = (c / g_reg_total) / (region_total[r] / all_reg_total) if g_reg_total and region_total[r] else None
            regions_out.append({"r": r, "n": c, "lq": round(lq, 2) if lq else None})

        cond_out = {}
        for y in occ_years:
            row = {k: cond.get((y, g, k), 0) for k in ("hours_H", "hours_D", "perm", "temp", "exp_1", "exp_0", "lang_en", "lang_other")}
            def frac(a, b):
                return r4(row[a] / (row[a] + row[b])) if row[a] + row[b] >= 20 else None
            cond_out[str(y)] = {"fulltime": frac("hours_H", "hours_D"), "permanent": frac("perm", "temp"),
                                "experience": frac("exp_1", "exp_0"), "english": frac("lang_en", "lang_other")}

        name_counts = sorted(names_by_g.get(g, {}).items(), key=lambda x: -x[1])
        titles = [{"t": tax["occupations"].get(o, {}).get("label", o), "n": c} for o, c in name_counts[:15]
                  if o in tax["occupations"]]
        emp_counts = sorted(emp_by_g.get(g, {}).items(), key=lambda x: -x[1])
        employers = [{"e": tidy_name(emp_names.get(e, e[2:] if e.startswith("n:") else e)), "n": c} for e, c in emp_counts[:12]]

        page = {
            "id": slug, "cid": g, "label": gi.get("label", g), "ssyk": gi.get("ssyk"), "field": gi.get("field"),
            "months": {ym_str(ym): c for ym, c in sorted(ym_counts.items()) if ym >= occ_first_ym},
            "ads": {"L12": ads_L12, "P12": ads_P12, "B12": ads_B12},
            "skills": skills_out[:120],
            "regions": regions_out,
            "conditions": cond_out,
            "titles": titles,
            "employers": employers,
        }
        occ_index.append({
            "id": slug, "cid": g, "label": page["label"], "ssyk": page["ssyk"], "field": page["field"],
            "L12": ads_L12, "P12": ads_P12, "B12": ads_B12,
            "years": {str(y): g_year.get(y, 0) for y in occ_years},
            "titles": [t["t"] for t in titles[:8]],
            "top": [s["s"] for s in skills_out if skill_meta[skill_index(skill_meta, s["s"])]["kind"] == "kompetens"][:4],
        })
        write_json(out / "occupations" / f"{slug}.json", page)

    # Related occupations by cosine similarity of what the job requires: skills and credentials, not
    # personal qualities, employment terms, languages or background checks (they appear everywhere).
    generic = {i for i, s in enumerate(skill_meta)
               if s["kind"] in ("egenskap", "villkor") or s["category"] in ("sprak", "krav")}
    vecs = {}
    for g, prof in profiles.items():
        v = {s: x for s, x in prof.items() if s not in generic}
        norm = math.sqrt(sum(x * x for x in v.values()))
        if norm and wsum(g_tot_ym[g], L12) >= 30:
            vecs[g] = (v, norm)
    related = {}
    keys = list(vecs)
    for g in keys:
        v, n = vecs[g]
        sims = []
        for h in keys:
            if h == g:
                continue
            w, m = vecs[h]
            dot = sum(x * w.get(s, 0) for s, x in v.items())
            sims.append((dot / (n * m), h))
        sims.sort(reverse=True)
        related[g] = [{"id": group_slug[h], "sim": round(sim, 3)} for sim, h in sims[:8] if sim > 0.3]
    for item in occ_index:
        p = out / "occupations" / f"{item['id']}.json"
        page = json.loads(p.read_text(encoding="utf-8"))
        page["related"] = related.get(item["cid"], [])
        write_json(p, page)

    # ---- skill pages
    skill_index_out = []
    nat_L12 = wsum(nat_ym, L12)
    for s, meta in enumerate(skill_meta):
        sc = s_ym.get(s, Counter())
        c_L12, c_P12, c_B12 = wsum(sc, L12), wsum(sc, P12), wsum(sc, B12)
        sy = yearly(sc)
        by_year = {str(y): r4(sy.get(y, 0) / nat_year[y]) for y in years if nat_year.get(y)}
        quarters = {}
        for q_end in range(last_ym, first_ym + 2, -3):
            win = range(q_end - 2, q_end + 1)
            denom = wsum(nat_ym, win)
            if denom:
                quarters[ym_str(q_end - 2)] = r4(wsum(sc, win) / denom)
        quarters = dict(sorted(quarters.items()))
        occ_rows = []
        for g, slug in group_slug.items():
            c = wsum(g_skill_ym[g].get(s, Counter()), L12)
            n = wsum(g_tot_ym[g], L12)
            if c >= MIN_SKILL_ADS and n:
                occ_rows.append({"o": slug, "n": c, "sh": r4(c / n)})
        by_count = sorted(occ_rows, key=lambda x: -x["n"])[:20]
        by_share = sorted([r for r in occ_rows if r["n"] >= 20], key=lambda x: -x["sh"])[:20]
        reg_rows = []
        for r in region_label:
            ry = [last_year] + ([last_year - 1] if partial_last_year else [])
            c = sum(reg_skill.get((y, r, s), 0) for y in ry)
            n = sum(reg_year_tot.get((y, r), 0) for y in ry)
            if n:
                reg_rows.append({"r": r, "n": c, "sh": r4(c / n)})
        # Co-occurrence: lift = P(a and b) / (P(a) P(b)), among ads that mention at least one skill.
        co = []
        if cooc_n.get(s, 0) >= 30:
            for t in range(n_skills):
                if t == s or cooc_n.get(t, 0) < 30:
                    continue
                a, b = (s, t) if s < t else (t, s)
                both = cooc.get(a * n_skills + b, 0)
                if both < 15:
                    continue
                lift = both * cooc_ads / (cooc_n[s] * cooc_n[t])
                co.append({"s": skill_meta[t]["id"], "n": both, "lift": round(lift, 2),
                           "p": r4(both / cooc_n[s])})
        co.sort(key=lambda x: -(x["p"] * math.log(max(x["lift"], 1.0001))))
        page = {
            **meta, "terms": skill_list[s]["terms"],
            "ads": {"L12": c_L12, "P12": c_P12, "B12": c_B12},
            "share": {"L12": r4(c_L12 / nat_L12) if nat_L12 else None,
                      "B12": r4(c_B12 / wsum(nat_ym, B12)) if wsum(nat_ym, B12) else None},
            "years": by_year, "quarters": quarters,
            "occupations": by_count, "occupationsByShare": by_share,
            "regions": sorted(reg_rows, key=lambda x: -x["sh"]),
            "related": co[:14],
        }
        write_json(out / "skills" / f"{meta['id']}.json", page)
        skill_index_out.append({**meta, "L12": c_L12, "B12": c_B12, "sh": page["share"]["L12"], "sh3": page["share"]["B12"],
                                "spark": [by_year.get(str(y)) for y in years],
                                "top": [r["o"] for r in by_count[:3]]})

    # ---- regions
    regions_out = []
    for r, lbl in sorted(region_label.items()):
        rym = {ym: c for (ym, rr), c in reg_ym.items() if rr == r}
        ry = [last_year] + ([last_year - 1] if partial_last_year else [])
        occ_rows = []
        reg_total_recent = sum(c for (y, g, rr), c in reg.items() if rr == r and y in ry)
        nat_total_recent = sum(c for (y, g, rr), c in reg.items() if rr != "00" and y in ry)
        g_recent = Counter()
        g_nat_recent = Counter()
        g_prev = Counter()
        for (y, g, rr), c in reg.items():
            if rr == "00" or g == "_none":
                continue
            if y in ry:
                g_nat_recent[g] += c
                if rr == r:
                    g_recent[g] += c
            if rr == r and y in [x - 3 for x in ry]:
                g_prev[g] += c
        for g, c in g_recent.most_common():
            if g not in group_slug:
                continue
            lq = (c / reg_total_recent) / (g_nat_recent[g] / nat_total_recent) if reg_total_recent else None
            occ_rows.append({"o": group_slug[g], "n": c, "lq": round(lq, 2) if lq else None, "prev": g_prev.get(g, 0)})
        skills_rows = []
        reg_ads_years = Counter()
        for (ym, rr), c in reg_ym.items():
            if rr == r:
                reg_ads_years[ym // 12] += c
        for s, meta in enumerate(skill_meta):
            c = sum(reg_skill.get((y, r, s), 0) for y in ry)
            cb = sum(reg_skill.get((y - 3, r, s), 0) for y in ry)
            n = sum(reg_ads_years[y] for y in ry)
            nb = sum(reg_ads_years[y - 3] for y in ry)
            if c >= 15 and n and nb:
                skills_rows.append({"s": meta["id"], "n": c, "sh": r4(c / n), "sh3": r4(cb / nb)})
        page = {"id": region_slug[r], "code": r, "label": lbl,
                "months": {ym_str(ym): c for ym, c in sorted(rym.items())},
                "occupations": occ_rows[:60], "skills": sorted(skills_rows, key=lambda x: -x["sh"])}
        write_json(out / "regions" / f"{region_slug[r]}.json", page)
        regions_out.append({"id": region_slug[r], "code": r, "label": lbl,
                            "L12": sum(rym.get(i, 0) for i in L12), "B12": sum(rym.get(i, 0) for i in B12)})

    # ---- fields
    fields_out = []
    for fid, f in tax["fields"].items():
        if f["deprecated"]:
            continue
        members = [o for o in occ_index if o["field"] == fid]
        if not members:
            continue
        fields_out.append({"id": slugify(f["label"]), "cid": fid, "label": f["label"],
                           "L12": sum(o["L12"] for o in members), "B12": sum(o["B12"] for o in members),
                           "occupations": [o["id"] for o in sorted(members, key=lambda o: -o["L12"])]})
    fields_out.sort(key=lambda f: -f["L12"])
    field_slug = {f["cid"]: f["id"] for f in fields_out}
    for o in occ_index:
        o["field"] = field_slug.get(o["field"])

    occ_index.sort(key=lambda o: -o["L12"])
    write_json(out / "occupations.json", occ_index)
    write_json(out / "skills.json", skill_index_out)
    write_json(out / "regions.json", regions_out)
    write_json(out / "fields.json", fields_out)
    write_json(out / "categories.json", vocab.categories)
    write_json(out / "kinds.json", vocab.kinds)

    meta = {
        "generated": date.today().isoformat(),
        "firstMonth": ym_str(first_ym), "lastMonth": ym_str(last_ym),
        "windows": {"L12": [ym_str(L12[0]), ym_str(L12[-1])], "P12": [ym_str(P12[0]), ym_str(P12[-1])],
                    "B12": [ym_str(B12[0]), ym_str(B12[-1])]},
        "years": years, "partialLastYear": partial_last_year, "occupationFirstYear": occ_first_year,
        "totalAds": stats["ads"], "dupesSkipped": stats["dupes"], "noGroup": stats["no_group"], "noRegion": stats["no_region"],
        "nationalMonths": {ym_str(ym): c for ym, c in sorted(nat_ym.items())},
        "nationalYears": {str(y): nat_year.get(y, 0) for y in years},
        "adsL12": nat_L12, "adsB12": nat_B12,
        "sources": sorted(m["source"] for m in metas),
        "skillCount": len(skill_meta), "occupationCount": len(occ_index),
    }
    write_json(out / "meta.json", meta)
    print(f"site data: {len(occ_index)} occupations, {len(skill_meta)} skills, {len(regions_out)} regions, "
          f"{len(fields_out)} fields -> {out}")


def skill_index(skill_meta, sid, _cache={}):
    if not _cache:
        _cache.update({s["id"]: i for i, s in enumerate(skill_meta)})
    return _cache[sid]


if __name__ == "__main__":
    main()
