# Engångsinställningar

Allt i koden är klart. Det här behöver göras av dig, eftersom det kräver inloggning
eller beslut som är dina. Allt ryms i gratisnivåerna.

## 0. Sajten är publicerad på <https://yrkestrender.se>

`.github/workflows/pages.yml` bygger och publicerar sajten på GitHub Pages vid varje
push till `main`. Domänen är kopplad under **Settings → Pages → Custom domain** i repot,
och den gamla adressen <https://skraggan.github.io/yrkestrender/> skickas vidare dit.

## 1. DNS hos Cloudflare (klart)

Under **yrkestrender.se → DNS → Records** i Cloudflare:

| Typ   | Namn  | Värde                 | Proxy    |
|-------|-------|-----------------------|----------|
| CNAME | `@`   | `skraggan.github.io`  | DNS only |
| CNAME | `www` | `skraggan.github.io`  | DNS only |

Cloudflare plattar ut CNAME-posten på roten till GitHubs IP-adresser. Ett CNAME kan
bara peka på ett värdnamn, aldrig på en sökväg som `/yrkestrender/`; att sajten ligger
på roten styrs av bygget (`BASE_PATH`), inte av DNS.

Låt proxyn vara avstängd (grå moln) så att GitHub kan utfärda HTTPS-certifikatet. När
certifikatet finns, kryssa i **Enforce HTTPS** under **Settings → Pages**. Vill du
sedan slå på Cloudflare-proxyn måste **SSL/TLS** stå på **Full (strict)**, annars blir
det en omdirigeringsloop.

## 2. Google Search Console (valfritt)

Lägg till domänen och skicka in `https://yrkestrender.se/sitemap-index.xml`.

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
