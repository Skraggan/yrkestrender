# Engångsinställningar

Allt i koden är klart. Det här behöver göras av dig, eftersom det kräver inloggning
eller beslut som är dina. Allt ryms i gratisnivåerna.

## 1. Publicera sajten på Cloudflare Pages (cirka 5 minuter)

1. Logga in på <https://dash.cloudflare.com> → **Workers & Pages** → **Create** →
   **Pages** → **Connect to Git**.
2. Välj repot **Skraggan/yrkestrender** och produktionsgrenen `main`.
3. Bygginställningar:
   - Framework preset: **Astro**
   - Build command: `npm run build`
   - Build output directory: `dist`
   - Miljövariabel (valfri): `SITE_URL` = sajtens adress, t.ex. `https://yrkestrender.se`
4. Spara. Första bygget tar 1–2 minuter. Sajten hamnar på
   `https://yrkestrender.pages.dev` (eller ett liknande namn om det är upptaget).

Om Cloudflare ger projektet ett annat namn än `yrkestrender`: ändra standardadressen i
`site.config.mjs` och `public/robots.txt`, eller sätt `SITE_URL` enligt ovan.

Varje push till `main` bygger om sajten, även de veckovisa datauppdateringarna.

## 2. Egen domän (valfritt, kostar bara domänen)

1. Köp t.ex. `yrkestrender.se` (kolla först att den är ledig).
2. Cloudflare Pages → projektet → **Custom domains** → lägg till domänen.
3. Sätt `SITE_URL=https://yrkestrender.se` i projektets miljövariabler och uppdatera
   `public/robots.txt`.
4. Google Search Console: lägg till domänen och skicka in `/sitemap-index.xml`.

## 3. Automatisk uppdatering (redan igång)

`.github/workflows/update.yml` körs varje måndag och behöver inga hemligheter. Den
använder `GITHUB_TOKEN` för att ladda upp faktafiler till releasen `facts` och checka in
ny data. Du kan köra den för hand under **Actions → Update data → Run workflow**.

Om något går fel syns det under Actions. Vanligaste orsaken är att JobTech har ändrat
filnamn eller format; `pipeline/update.py --dry-run` visar vad skriptet ser.

## 4. Ändra kompetenslistan

Redigera `pipeline/vocab/skills.toml` och kör `python3 -I pipeline/update.py` lokalt (eller
låt måndagskörningen göra det):

- Flytta, byt namn på eller slå ihop kompetenser: bara omräkning, går på en minut.
- Nya termer: skriptet läser om annonsfilerna, ungefär 15 minuter lokalt eller ett par
  timmar i GitHub Actions.

`pipeline/vocab/term_ids.json` får bara växa. Ta aldrig bort rader där, även om termen
tas bort ur listan.
