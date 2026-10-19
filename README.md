# Yrkestrender

Vad efterfrågar arbetsgivarna? Yrkestrender visar hur ofta platsannonser i Sverige
nämner olika kompetenser, körkort, språk, utbildningar och villkor, för varje yrke,
län och år sedan 2006.

Byggt på Arbetsförmedlingens historiska annonser från
[JobTech Development](https://data.jobtechdev.se/annonser/historiska/) (CC0).

## Så hänger det ihop

```
JobTech (≈10 GB zip, 2006–nu)
   │  pipeline/extract.py     läser annonstexten EN gång
   ▼
data/facts/*.jsonl.gz       en rad per annons: datum, yrke, ort, arbetsgivare,
   │                         villkor och id för varje term som hittades
   │  pipeline/aggregate.py   några minuter, ingen annonstext
   ▼
data/site/*.json            det sajten byggs av (incheckat)
   │  Astro
   ▼
dist/                       statisk sajt (Cloudflare Pages)
```

- **Kompetenslistan** finns i `pipeline/vocab/skills.toml`: ~475 saker i 20
  kategorier med de ord som räknas. Kategorierna hör till fyra sorter som visas och
  jämförs var för sig: kompetenser, krav och behörigheter, personliga egenskaper samt
  villkor och förmåner. Varje term får ett permanent id i `pipeline/vocab/term_ids.json`.
- **Trender** visas främst mot snittet: en andels förändring utöver hur alla saker av
  samma sort förändrats, och antal annonser mot arbetsmarknaden i stort
  (`src/lib/trend.ts`). Den totala förändringen visas som andra siffra.
- **Äldre yrkeskoder** som saknas i JobTechs taxonomi kopplas till yrken utifrån
  annonsrubriker (`pipeline/tools/legacy_map.py` → `data/legacy_groups.json`).
- **Ändra utan att läsa om annonserna:** byta namn på, flytta eller slå ihop
  kompetenser, eller flytta termer mellan dem, kräver bara `aggregate.py`.
- **Nya termer:** `update.py` ser att faktafilerna skapades innan termen fanns och
  läser bara om de filerna.
- **Faktafilerna** sparas som tillgångar på GitHub-releasen `facts`, så
  uppdateringar i GitHub Actions läser bara nya annonsfiler.

## Kommandon

```bash
npm install
npm run dev          # utvecklingsserver
npm run build        # bygger dist/
npm test             # vitest
python3 -I -m unittest discover -s pipeline/tests -t pipeline
```

Datapipeline (Python 3.11+, bara standardbiblioteket):

```bash
python3 -I pipeline/taxonomy.py data/taxonomy.json   # yrkes- och ortskoder från JobTech
python3 -I pipeline/update.py --dry-run              # vad behöver göras?
python3 -I pipeline/update.py                        # hämta nytt, extrahera, aggregera (lokalt)
python3 -I pipeline/update.py --store github         # samma, med fakta i GitHub-releasen
python3 -I pipeline/aggregate.py                     # bara räkna om data/site
```

Första körningen från noll laddar ner ungefär 10 GB och tar runt 30 minuter på 8 kärnor.

## Automatisk uppdatering

`.github/workflows/update.yml` körs varje måndag. Den kollar om JobTech har nya
eller ändrade filer, extraherar bara dem, laddar upp faktan till releasen `facts`,
räknar om `data/site` och checkar in. Cloudflare Pages bygger om vid varje push.

Se [SETUP.md](SETUP.md) för det som behöver göras en gång.
