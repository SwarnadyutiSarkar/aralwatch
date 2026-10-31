# AralWatch — Central Asian Drought Intelligence
Interactive map + dashboard of drought indices (SPI-3, SPI-12), 30-day rainfall anomalies, 10-year SPI history and 1991–present precipitation trends for 31 regions across Kazakhstan, Uzbekistan, Kyrgyzstan, Tajikistan and Turkmenistan, highlighting agricultural regions.

**Live site:** `https://<your-username>.github.io/aralwatch/`

## How it works
`scripts/build_data.py` pulls ERA5 daily precipitation/ET0 (Open-Meteo Historical Weather API), computes SPI against a 1991–2020 gamma baseline and writes `data/drought.json`. A GitHub Action (`.github/workflows/update-data.yml`) re-runs it daily and commits the result; the static site (`index.html`, Leaflet + Chart.js) reads that file.

## Run locally
```
pip install numpy pandas scipy requests
python scripts/build_data.py          # live data
python -m http.server 8000            # open http://localhost:8000
```
Use `--demo` for synthetic data (the site shows a banner when demo data is loaded).

## Data & limitations
ERA5 reanalysis (ECMWF/Copernicus C3S), ~5–7 day latency. Values are point (grid-cell) samples at regional centres, not area averages. Not an official drought monitor.
