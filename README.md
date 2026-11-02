# AralWatch — Global Drought & Rainfall Intelligence
Interactive world map and dashboard: SPI-3 / SPI-12 drought indices, 30-day rainfall anomaly, SPI history and long-term rainfall trends for ~195 countries plus 31 Central Asian agricultural focus points. Filter by continent, subregion, country, search or agricultural focus.

**Stack:** React + TypeScript + Vite + Tailwind, Leaflet, Chart.js; Python data pipeline; GitHub Actions + GitHub Pages.

## Architecture
- `scripts/build_data.py` — pulls ERA5 daily precipitation (Open-Meteo Historical Weather API, `models=era5`), keeps a compact store in `data/store.json`, computes SPI (gamma fit, 1991–2020 baseline) and writes `data/drought.json` and `data/briefing.json`. Runs every 6 hours (`.github/workflows/update-data.yml`).
- `src/` — the React app. At deploy time (`.github/workflows/deploy.yml`) the latest `data/*.json` is copied into the build and the site is published to GitHub Pages.

## Run locally
    pip install numpy pandas scipy requests
    python scripts/build_data.py --demo        # synthetic data, testing only
    mkdir -p public/data && cp data/drought.json data/briefing.json public/data/
    npm install && npm run dev

## Limits
ERA5 reanalysis, ~5–7 day latency. Each marker is one grid-cell sample (country centre point or an agricultural focus point), not an area average. Not an official drought monitor.
