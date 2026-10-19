"""Fetch the parts of JobTech's taxonomy the site needs and save them as JSON.

- occupation names (including deprecated ones with their legacy ids), each with
  its occupation group (SSYK level 4)
- occupation groups with SSYK code and occupation field
- municipalities with their region (län)

Older ads (2006–2018) only carry legacy occupation ids, so the legacy -> group
mapping is what lets every year be counted per occupation group.

Usage: python3 -I pipeline/taxonomy.py data/taxonomy.json
"""
import json
import sys
import time
import urllib.parse
import urllib.request

API = "https://taxonomy.api.jobtechdev.se/v1/taxonomy/graphql"


def gql(query):
    url = API + "?" + urllib.parse.urlencode({"query": query})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                data = json.load(r)
            if "errors" in data:
                raise RuntimeError(data["errors"])
            return data["data"]
        except Exception as e:  # noqa: BLE001 - retry any network/API error
            if attempt == 4:
                raise
            print(f"retrying taxonomy query ({e})", file=sys.stderr)
            time.sleep(3 * (attempt + 1))


def fetch():
    occ = gql("""{concepts(type:"occupation-name", include_deprecated:true){
        id preferred_label deprecated deprecated_legacy_id
        broader(type:"ssyk-level-4"){id}
        replaced_by{id}
    }}""")["concepts"]
    groups = gql("""{concepts(type:"ssyk-level-4", include_deprecated:true){
        id preferred_label deprecated ssyk_code_2012 deprecated_legacy_id
        broader(type:"occupation-field"){id}
        replaced_by{id}
    }}""")["concepts"]
    fields = gql("""{concepts(type:"occupation-field", include_deprecated:true){
        id preferred_label deprecated deprecated_legacy_id
    }}""")["concepts"]
    munis = gql("""{concepts(type:"municipality", include_deprecated:true){
        id preferred_label lau_2_code_2015
        broader(type:"region"){id preferred_label national_nuts_level_3_code_2019}
    }}""")["concepts"]
    return occ, groups, fields, munis


def build(occ, groups, fields, munis):
    out = {"occupations": {}, "legacy_occupations": {}, "groups": {}, "fields": {}, "municipalities": {}, "regions": {}}
    occ_by_id = {o["id"]: o for o in occ}

    def group_of(o, depth=0):
        if o["broader"]:
            return o["broader"][0]["id"]
        # Deprecated names may lack a group; follow replaced_by.
        for r in o.get("replaced_by") or []:
            if depth < 3 and r["id"] in occ_by_id:
                g = group_of(occ_by_id[r["id"]], depth + 1)
                if g:
                    return g
        return None

    for o in occ:
        g = group_of(o)
        out["occupations"][o["id"]] = {"label": o["preferred_label"], "group": g, "deprecated": o["deprecated"]}
        if o.get("deprecated_legacy_id"):
            out["legacy_occupations"][o["deprecated_legacy_id"]] = o["id"]
    for g in groups:
        out["groups"][g["id"]] = {
            "label": g["preferred_label"],
            "ssyk": g.get("ssyk_code_2012"),
            "field": g["broader"][0]["id"] if g["broader"] else None,
            "deprecated": g["deprecated"],
            "replaced_by": [r["id"] for r in g.get("replaced_by") or []],
        }
    for f in fields:
        out["fields"][f["id"]] = {"label": f["preferred_label"], "deprecated": f["deprecated"],
                                  "legacy": f.get("deprecated_legacy_id")}
    for m in munis:
        code = m.get("lau_2_code_2015")
        if not code:
            continue
        reg = m["broader"][0] if m["broader"] else None
        out["municipalities"][code] = {"label": m["preferred_label"], "region": reg and reg["national_nuts_level_3_code_2019"]}
        if reg:
            out["regions"][reg["national_nuts_level_3_code_2019"]] = reg["preferred_label"]
    return out


def main(path):
    tax = build(*fetch())
    with open(path, "w", encoding="utf-8") as f:
        json.dump(tax, f, ensure_ascii=False, indent=0, sort_keys=True)
    print({k: len(v) for k, v in tax.items()})


if __name__ == "__main__":
    main(sys.argv[1])
