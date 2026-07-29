# Polly's Trade Tools — Live Price Feed Setup

This connects the three trade tools to real, periodically-refreshed UEX data
instead of the hardcoded snapshot, using a small script + GitHub Actions.

## How it works

1. `fetch_uex_prices.py` calls the UEX API 2.0 (`commodities_prices_all`) and
   writes `data/prices.json`.
2. A GitHub Actions workflow (`.github/workflows/update-prices.yml`) runs this
   script every hour and commits the updated `data/prices.json`.
3. GitHub Pages serves the whole repo (HTML tools + `data/prices.json`) from
   the same domain, so the tools can `fetch('./data/prices.json')` with no
   CORS issues.
4. Each HTML tool tries to load `data/prices.json` on startup. If that
   succeeds, it overrides the hardcoded snapshot prices/stock with the live
   ones (keeping the curated distances/destinations, which the API doesn't
   provide). If it fails (e.g. opened directly in Claude.ai, or offline), it
   silently falls back to the hardcoded snapshot — nothing breaks either way.

## Setup steps

1. **Create a new GitHub repository** (public or private — Pages works with
   either, private repos need GitHub Pro/Team/Enterprise for Pages).

2. **Add these files to the repo root:**
   - `fetch_uex_prices.py`
   - `.github/workflows/update-prices.yml`
   - The three HTML tools (or the combined `trade-tools-combined.html`)

3. **Add your UEX API token as a repository secret** — never commit it to a
   file:
   - Repo → Settings → Secrets and variables → Actions → New repository secret
   - Name: `UEX_API_TOKEN`
   - Value: your Bearer token from https://uexcorp.space/api/apps
   - **If you already pasted this token anywhere outside this secret (chat,
     notes, etc.), generate a new one on that page and delete the old one.**

4. **Run the workflow once manually** to generate the first `data/prices.json`:
   - Repo → Actions → "Update UEX Prices" → Run workflow
   - Check the run log — it prints a warning for any station name that didn't
     match anything in the API response, so you can adjust
     `STATIONS_OF_INTEREST` in `fetch_uex_prices.py` if UEX renamed something.

5. **Enable GitHub Pages:**
   - Repo → Settings → Pages → Source: "Deploy from a branch" → `main` / `(root)`
   - Your tools will be live at `https://<your-username>.github.io/<repo>/`

6. Open the tools from that GitHub Pages URL (not from Claude.ai) so the
   `fetch()` call actually works — the Claude.ai artifact sandbox blocks
   outbound network calls, so the live feed only works once it's hosted as a
   normal website like this.

## Maintenance

- The workflow runs unattended every hour. No further action needed unless
  UEX renames a terminal (the Action log will warn you).
- To add a new station, add it to `STATIONS_OF_INTEREST` in
  `fetch_uex_prices.py` and to the tool's own station/material list.
