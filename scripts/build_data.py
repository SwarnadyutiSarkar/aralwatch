#!/usr/bin/env python3
"""AralWatch pipeline: ERA5 daily precipitation (via Open-Meteo archive API) -> drought indicators JSON.
Usage: python scripts/build_data.py            (live data)
       python scripts/build_data.py --demo     (synthetic data, for local testing only)"""
import json, sys, time, datetime as dt
from pathlib import Path
import numpy as np, pandas as pd, requests
from scipy import stats

START, B0, B1, LAG, N = "1991-01-01", 1991, 2020, 7, 120
API = "https://archive-api.open-meteo.com/v1/archive"
DEMO = "--demo" in sys.argv
# (name, country, lat, lon, agricultural focus or "")
PTS = [
 ("Astana","KZ",51.17,71.43,"Rainfed wheat"),("Kostanay","KZ",53.21,63.62,"Grain belt"),
 ("Aktobe","KZ",50.28,57.21,"Wheat / pasture"),("Pavlodar","KZ",52.29,76.97,"Grain / fodder"),
 ("Karaganda","KZ",49.80,73.10,""),("Almaty","KZ",43.24,76.89,"Orchards / irrigated"),
 ("Shymkent","KZ",42.32,69.59,"Cotton / wheat"),("Kyzylorda","KZ",44.85,65.51,"Syr Darya rice"),
 ("Atyrau","KZ",47.11,51.92,""),("Aktau","KZ",43.65,51.15,""),
 ("Tashkent","UZ",41.30,69.24,"Irrigated mixed"),("Fergana","UZ",40.38,71.78,"Cotton / orchards"),
 ("Samarkand","UZ",39.65,66.96,"Cereals / orchards"),("Bukhara","UZ",39.77,64.42,"Cotton"),
 ("Urgench","UZ",41.55,60.63,"Khorezm cotton / rice"),("Nukus","UZ",42.46,59.60,"Aral Sea delta"),
 ("Termez","UZ",37.22,67.28,""),
 ("Bishkek","KG",42.87,74.59,"Chui valley crops"),("Osh","KG",40.53,72.80,"Fergana valley"),
 ("Talas","KG",42.52,72.24,"Irrigated crops"),("Karakol","KG",42.49,78.39,"Issyk-Kul agriculture"),
 ("Naryn","KG",41.43,75.99,""),
 ("Dushanbe","TJ",38.56,68.77,""),("Khujand","TJ",40.28,69.62,"Cotton / fruit"),
 ("Kulob","TJ",37.91,69.78,"Khatlon cotton / wheat"),("Khorog","TJ",37.49,71.55,""),
 ("Ashgabat","TM",37.96,58.33,""),("Mary","TM",37.60,61.83,"Murghab cotton / wheat"),
 ("Turkmenabat","TM",39.07,63.58,"Amu Darya cotton"),("Dashoguz","TM",41.84,59.97,"Cotton / wheat"),
 ("Balkanabat","TM",39.51,54.37,""),
]

S = requests.Session()

def fetch(p, end):
    """One location per request, precipitation only: small, fast, and retried on timeouts/rate limits."""
    q = dict(latitude=p[2], longitude=p[3], start_date=START, end_date=end, daily="precipitation_sum", timezone="UTC")
    err = None
    for a in range(6):
        try:
            r = S.get(API, params=q, timeout=90)
            if r.status_code == 200: return r.json()
            err = f"HTTP {r.status_code}: {r.text[:120]}"
        except requests.RequestException as e:
            err = repr(e)[:150]
        wait = 20 * (a + 1); print(f"  {p[0]}: {err} -> retry in {wait}s", flush=True); time.sleep(wait)
    raise RuntimeError(f"{p[0]} failed after retries: {err}")

def demo(p, end):
    rng = np.random.default_rng(abs(hash(p[0])) % 1000); d = pd.date_range(START, end); doy = d.dayofyear.values
    pr = rng.gamma(.4, 6, len(d)) * (np.sin((doy - 60) / 365 * 2 * np.pi) * .4 + .6) * (rng.random(len(d)) < .3)
    return {"daily": {"time": [x.strftime("%Y-%m-%d") for x in d], "precipitation_sum": pr.tolist()}}

def spi(s, k):
    r = s.rolling(k).sum(); out = pd.Series(np.nan, index=r.index)
    for m in range(1, 13):
        x = r[r.index.month == m].dropna()
        b = x[(x.index.year >= B0) & (x.index.year <= B1)]
        pos = b[b > 0.01]
        if len(pos) < 10: continue
        q = (b <= 0.01).mean(); a, _, sc = stats.gamma.fit(pos, floc=0)
        F = q + (1 - q) * stats.gamma.cdf(x.clip(lower=0.01), a, loc=0, scale=sc)
        out[x.index] = np.clip(stats.norm.ppf(np.clip(F, 1e-4, 1 - 1e-4)), -3, 3)
    return out

def anom30(p):
    """Last-30-day rainfall as % of the 1991-2020 mean for the same calendar window."""
    last = p.index.max(); cur = p[last - pd.Timedelta(days=29):last].sum(); base = []
    for y in range(B0, B1 + 1):
        e = pd.Timestamp(year=y, month=last.month, day=min(last.day, 28))
        base.append(p[e - pd.Timedelta(days=29):e].sum())
    m = np.mean(base)
    return None if m < 1 else round(100 * (cur - m) / m, 1)

def process(j):
    df = pd.DataFrame(j["daily"]); df["time"] = pd.to_datetime(df["time"])
    df = df.set_index("time").dropna(subset=["precipitation_sum"]); p = df["precipitation_sum"]; last = p.index.max()
    m = p.resample("MS").sum(); m = m[(m.index + pd.offsets.MonthEnd(0)) <= last]
    s3, s12 = spi(m, 3), spi(m, 12)
    ann = m.groupby(m.index.year).agg(["sum", "count"]); ann = ann[ann["count"] == 12]["sum"]
    return dict(last=last, months=[d.strftime("%Y-%m") for d in s3.index[-N:]],
                spi3=[round(v, 2) for v in s3.iloc[-N:]], spi12=[None if np.isnan(v) else round(v, 2) for v in s12.iloc[-N:]],
                years=[int(y) for y in ann.index], annual=[round(v) for v in ann.values],
                anom30=anom30(p))

def main():
    end = (dt.date.today() - dt.timedelta(days=LAG)).isoformat(); pts = []; meta = None; failed = []
    for p in PTS:
        n, c, la, lo, crop = p
        try:
            r = process((demo if DEMO else fetch)(p, end))
        except Exception as e:
            print("SKIP", n, e, flush=True); failed.append(n); continue
        meta = meta or r
        pts.append(dict(id=n.lower(), name=n, country=c, lat=la, lon=lo, crop=crop, ag=bool(crop),
                        spi3=r["spi3"][-1], spi12=r["spi12"][-1], anom30=r["anom30"],
                        s3=r["spi3"], s12=r["spi12"], annual=r["annual"]))
        print(f"{len(pts)}/{len(PTS)} {n}", flush=True); time.sleep(1.5)
    if len(pts) < 0.8 * len(PTS): sys.exit(f"Too many failures ({failed}); not overwriting data")
    out = dict(generated=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), demo=DEMO,
               data_through=str(meta["last"].date()), baseline=f"{B0}-{B1}", months=meta["months"], years=meta["years"],
               source="ECMWF ERA5 reanalysis via Open-Meteo Historical Weather API", points=pts)
    f = Path(__file__).resolve().parent.parent / "data" / "drought.json"; f.parent.mkdir(exist_ok=True)
    f.write_text(json.dumps(out, separators=(",", ":"))); print("wrote", f, f.stat().st_size // 1024, "KB", "skipped:", failed)

if __name__ == "__main__": main()
