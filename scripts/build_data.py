#!/usr/bin/env python3
"""AralWatch global pipeline: ERA5 (via Open-Meteo archive API) -> drought indicators, incremental & rate-limit aware.
Each run: (1) seed up to BATCH new locations with full 1991->today history, (2) refresh the recent days/months of
already-seeded locations, (3) rebuild data/drought.json from data/store.json.
  python scripts/build_data.py          live
  python scripts/build_data.py --demo   synthetic data (testing only)"""
import json, os, sys, time, datetime as dt
from pathlib import Path
import numpy as np, pandas as pd, requests
from scipy import stats

DATA = Path(__file__).resolve().parent.parent / "data"
START, B0, B1, LAG, N, WIN = "1991-01-01", 1991, 2020, 7, 120, 100
BATCH = int(os.environ.get("BATCH") or 40)
API = "https://archive-api.open-meteo.com/v1/archive"
DEMO = "--demo" in sys.argv
S = requests.Session()
class Stop(Exception): pass

CN = {"KZ": "Kazakhstan", "UZ": "Uzbekistan", "KG": "Kyrgyzstan", "TJ": "Tajikistan", "TM": "Turkmenistan"}
# Central Asian agricultural focus points (name, ISO, lat, lon, agricultural focus or "")
CA = [
 ("Astana","KZ",51.17,71.43,"Rainfed wheat"),("Kostanay","KZ",53.21,63.62,"Grain belt"),("Aktobe","KZ",50.28,57.21,"Wheat / pasture"),
 ("Pavlodar","KZ",52.29,76.97,"Grain / fodder"),("Karaganda","KZ",49.80,73.10,""),("Almaty","KZ",43.24,76.89,"Orchards / irrigated"),
 ("Shymkent","KZ",42.32,69.59,"Cotton / wheat"),("Kyzylorda","KZ",44.85,65.51,"Syr Darya rice"),("Atyrau","KZ",47.11,51.92,""),
 ("Aktau","KZ",43.65,51.15,""),("Tashkent","UZ",41.30,69.24,"Irrigated mixed"),("Fergana","UZ",40.38,71.78,"Cotton / orchards"),
 ("Samarkand","UZ",39.65,66.96,"Cereals / orchards"),("Bukhara","UZ",39.77,64.42,"Cotton"),("Urgench","UZ",41.55,60.63,"Khorezm cotton / rice"),
 ("Nukus","UZ",42.46,59.60,"Aral Sea delta"),("Termez","UZ",37.22,67.28,""),("Bishkek","KG",42.87,74.59,"Chui valley crops"),
 ("Osh","KG",40.53,72.80,"Fergana valley"),("Talas","KG",42.52,72.24,"Irrigated crops"),("Karakol","KG",42.49,78.39,"Issyk-Kul agriculture"),
 ("Naryn","KG",41.43,75.99,""),("Dushanbe","TJ",38.56,68.77,""),("Khujand","TJ",40.28,69.62,"Cotton / fruit"),
 ("Kulob","TJ",37.91,69.78,"Khatlon cotton / wheat"),("Khorog","TJ",37.49,71.55,""),("Ashgabat","TM",37.96,58.33,""),
 ("Mary","TM",37.60,61.83,"Murghab cotton / wheat"),("Turkmenabat","TM",39.07,63.58,"Amu Darya cotton"),
 ("Dashoguz","TM",41.84,59.97,"Cotton / wheat"),("Balkanabat","TM",39.51,54.37,""),
]
REGIONS = [dict(id="r-" + n.lower(), name=n, country=CN[c], iso=c, continent="Asia", subregion="Central Asia",
                lat=la, lon=lo, kind="region", crop=crop) for n, c, la, lo, crop in CA]

def countries():
    f = DATA / "countries.json"
    if DEMO:
        return [dict(id="c-" + i.lower(), name=n, country=n, iso=i, continent=ct, subregion=sr, lat=la, lon=lo, kind="country", crop="")
                for n, i, ct, sr, la, lo in [("Brazil","BR","South America","South America",-10,-55),("Kenya","KE","Africa","Eastern Africa",1,38),
                ("India","IN","Asia","Southern Asia",21,78),("France","FR","Europe","Western Europe",46,2),("Australia","AU","Oceania","Australia and New Zealand",-27,133),
                ("Egypt","EG","Africa","Northern Africa",27,30)]]
    try:
        r = requests.get("https://restcountries.com/v3.1/all", timeout=60,
                         params={"fields": "name,cca2,region,subregion,continents,latlng,independent"}); r.raise_for_status()
        out = [dict(id="c-" + c["cca2"].lower(), name=c["name"]["common"], country=c["name"]["common"], iso=c["cca2"],
                    continent=(c.get("continents") or [c["region"]])[0], subregion=c.get("subregion") or c["region"],
                    lat=c["latlng"][0], lon=c["latlng"][1], kind="country", crop="")
               for c in r.json() if c.get("independent") and c.get("latlng") and c.get("region") not in (None, "", "Antarctic")]
        out.sort(key=lambda c: c["name"]); f.write_text(json.dumps(out)); return out
    except Exception as e:
        if f.exists(): print("countries: using cached list:", e); return json.loads(f.read_text())
        raise

def fetch(lat, lon, start, end):
    q = dict(latitude=lat, longitude=lon, start_date=start, end_date=end, daily="precipitation_sum", models="era5", timezone="UTC")
    err = None
    for a in range(5):
        try:
            r = S.get(API, params=q, timeout=90)
            if r.status_code == 200: return r.json()
            err = f"HTTP {r.status_code}: {r.text[:110]}"
            if r.status_code == 429 and "aily" in r.text: raise Stop(err)      # daily quota used up: stop cleanly
        except requests.RequestException as e:
            err = repr(e)[:120]
        wait = 20 * (a + 1); print(f"  ({lat},{lon}) {err} -> retry in {wait}s", flush=True); time.sleep(wait)
    raise RuntimeError(err)

def demo_fetch(lat, lon, start, end):
    rng = np.random.default_rng(int(abs(lat) * 1000 + abs(lon) * 7)); d = pd.date_range(START, end); doy = d.dayofyear.values
    pr = rng.gamma(.4, 6, len(d)) * (np.sin((doy - 60) / 365 * 2 * np.pi) * .4 + .6) * (rng.random(len(d)) < .3)
    s = pd.Series(pr, index=d)[start:]
    return {"daily": {"time": [x.strftime("%Y-%m-%d") for x in s.index], "precipitation_sum": s.tolist()}}

def daily_series(j):
    d = pd.DataFrame(j["daily"]); d["time"] = pd.to_datetime(d["time"])
    return d.set_index("time")["precipitation_sum"].dropna()

def build_store(p):
    """Full-history seed: monthly totals, 30-day climatology by day-of-year, last 60 daily values."""
    last = p.index.max(); m = p.resample("MS").sum(); m = m[(m.index + pd.offsets.MonthEnd(0)) <= last]
    r30 = p.rolling(30).sum(); b = r30[(r30.index.year >= B0) & (r30.index.year <= B1)]
    c30 = b.groupby(b.index.dayofyear).mean().reindex(range(1, 367)).interpolate().bfill().ffill().round(1).tolist()
    t = p.iloc[-60:]
    return dict(m0=m.index[0].strftime("%Y-%m"), m=[round(v, 1) for v in m.values], c30=c30,
                d0=str(t.index[0].date()), d=[round(v, 1) for v in t.values])

def refresh(st, loc, end, fetcher):
    """Cheap incremental update (last ~100 days). Returns None if the stored history has a gap (-> reseed)."""
    ws = (pd.Timestamp(end) - pd.Timedelta(days=WIN)).strftime("%Y-%m-%d")
    p = daily_series(fetcher(loc["lat"], loc["lon"], ws, end)); last = p.index.max()
    mn = p.resample("MS").sum(); mn = mn[(mn.index >= p.index.min()) & (mn.index + pd.offsets.MonthEnd(0) <= last)]
    old = pd.Series(st["m"], index=pd.period_range(st["m0"], periods=len(st["m"]), freq="M").to_timestamp())
    new = pd.concat([old[~old.index.isin(mn.index)], mn]).sort_index()
    if len(new) != (new.index[-1].year - new.index[0].year) * 12 + new.index[-1].month - new.index[0].month + 1: return None
    t = p.iloc[-60:]
    st.update(m=[round(v, 1) for v in new.values], d0=str(t.index[0].date()), d=[round(v, 1) for v in t.values]); return st

def spi(s, k):
    r = s.rolling(k).sum(); out = pd.Series(np.nan, index=r.index)
    for m in range(1, 13):
        x = r[r.index.month == m].dropna(); b = x[(x.index.year >= B0) & (x.index.year <= B1)]; pos = b[b > 0.01]
        if len(pos) < 10: continue
        q = (b <= 0.01).mean(); a, _, sc = stats.gamma.fit(pos, floc=0)
        F = q + (1 - q) * stats.gamma.cdf(x.clip(lower=0.01), a, loc=0, scale=sc)
        out[x.index] = np.clip(stats.norm.ppf(np.clip(F, 1e-4, 1 - 1e-4)), -3, 3)
    return out

def derive(loc, st, upto):
    m = pd.Series(st["m"], index=pd.period_range(st["m0"], periods=len(st["m"]), freq="M").to_timestamp())
    m = m.reindex(pd.date_range(m.index[0], upto, freq="MS"))
    ann = m.groupby(m.index.year).agg(["sum", "count"]); ann = ann[ann["count"] == 12]["sum"]
    arid = bool(ann.mean() < 100)                       # SPI is unreliable in hyper-arid climates
    s3, s12 = spi(m, 3), spi(m, 12)
    if arid: s3[:] = np.nan; s12[:] = np.nan
    d = pd.Series(st["d"], index=pd.date_range(st["d0"], periods=len(st["d"])))
    clim = st["c30"][d.index[-1].dayofyear - 1]; an = None if clim < 1 else round(100 * (d.iloc[-30:].sum() - clim) / clim, 1)
    cl = lambda s: [None if np.isnan(v) else round(float(v), 2) for v in s.iloc[-N:]]
    pt = dict(loc, ag=bool(loc["crop"]), spi3=cl(s3)[-1], spi12=cl(s12)[-1], anom30=an, arid=arid, s3=cl(s3), s12=cl(s12),
              y0=int(ann.index[0]), annual=[round(v) for v in ann.values], mean=round(float(ann.mean())), cv=round(float(ann.std() / ann.mean()), 2))
    return pt, [x.strftime("%Y-%m") for x in s3.index[-N:]]

def facts(pts, through):
    ok = [p for p in pts if p["spi3"] is not None]; dr = [p for p in ok if p["spi3"] <= -1]
    c = [p for p in ok if p["kind"] == "country"]; ag = [p for p in ok if p["kind"] == "region"]
    b = lambda p: dict(name=p["name"], country=p["country"], spi3=p["spi3"], spi12=p["spi12"], rain30_pct=p["anom30"])
    cont = {}
    for p in c:
        a = cont.setdefault(p["continent"], {"in_drought": 0, "total": 0}); a["total"] += 1; a["in_drought"] += p["spi3"] <= -1
    chg = sorted(((p["s3"][-1] - p["s3"][-2], p) for p in ok if p["s3"][-1] is not None and p["s3"][-2] is not None), key=lambda x: x[0])
    return dict(data_through=through, n_locations=len(ok), n_drought=len(dr),
                persistent_drought=len([p for p in ok if p["spi12"] is not None and p["spi3"] <= -1 and p["spi12"] <= -1]),
                by_continent=cont, driest=[b(p) for p in sorted(c, key=lambda p: p["spi3"])[:5]],
                wettest=[b(p) for p in sorted(c, key=lambda p: -p["spi3"])[:3]],
                worsening=[dict(b(p), change_vs_last_month=round(d, 2)) for d, p in chg[:3] if d < -0.5],
                central_asia=dict(ag_total=len(ag), ag_in_drought=len([p for p in ag if p["spi3"] <= -1]),
                                  driest=[b(p) for p in sorted(ag, key=lambda p: p["spi3"])[:3]]))

def rule_text(f):
    pc = round(100 * f["n_drought"] / max(f["n_locations"], 1))
    t = [f"As of {f['data_through']}, {f['n_drought']} of {f['n_locations']} monitored locations ({pc}%) show moderate or worse short-term drought (SPI-3 at or below -1); {f['persistent_drought']} are also dry over 12 months."]
    if f["driest"]: t.append("Driest countries right now: " + ", ".join(f"{x['name']} (SPI-3 {x['spi3']:+.2f})" for x in f["driest"][:3]) + ".")
    cs = [(v["in_drought"] / v["total"], k, v) for k, v in f["by_continent"].items() if v["total"] >= 3]
    if cs: r, k, v = max(cs); t.append(f"{k} has the highest share of countries in drought ({v['in_drought']} of {v['total']}).")
    if f["worsening"]: t.append("Fastest deterioration versus last month: " + ", ".join(f"{x['name']} ({x['change_vs_last_month']:+.2f} SPI)" for x in f["worsening"]) + ".")
    ca = f["central_asia"]
    if ca["ag_total"]: t.append(f"In Central Asia, {ca['ag_in_drought']} of {ca['ag_total']} agricultural focus areas are under drought stress" + (", led by " + ", ".join(x["name"] for x in ca["driest"][:2] if x["spi3"] <= -1) if ca["ag_in_drought"] else "") + ".")
    return " ".join(t)

def llm_text(f):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key or DEMO: return None
    prompt = ("You are a climate analyst writing a short public situation briefing for a drought dashboard. Use ONLY the figures in the JSON; "
              "never invent numbers, causes, forecasts or events. 120-180 words: two short paragraphs, then one line starting 'Watch:' naming up to 3 locations. "
              "SPI-3 <= -1 means moderate drought or worse; rain30_pct is last-30-day rainfall relative to the 1991-2020 normal. "
              "Mention once that values are ERA5 point samples.\n\nDATA:\n" + json.dumps(f))
    try:
        r = requests.post("https://api.anthropic.com/v1/messages", timeout=90,
                          headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                          json={"model": os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5"), "max_tokens": 600, "messages": [{"role": "user", "content": prompt}]})
        r.raise_for_status()
        return "".join(x.get("text", "") for x in r.json()["content"] if x.get("type") == "text").strip() or None
    except Exception as e:
        print("Claude briefing failed, using rule-based text:", str(e)[:150]); return None

def briefing(pts, through):
    f = facts(pts, through); bf = DATA / "briefing.json"
    if bf.exists():
        old = json.loads(bf.read_text())
        if old.get("method") == "claude" and old["facts"]["data_through"] == through and old["facts"]["n_locations"] == f["n_locations"]: return
    txt = llm_text(f); method = "claude" if txt else "rules"
    bf.write_text(json.dumps(dict(generated=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), method=method,
                  model=os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5") if txt else None, text=txt or rule_text(f), facts=f), indent=1))
    print("briefing written:", method)

def main():
    DATA.mkdir(exist_ok=True); f = (demo_fetch if DEMO else fetch)
    end = (dt.date.today() - dt.timedelta(days=LAG)).isoformat(); locs = REGIONS + countries()
    sf = DATA / "store.json"; store = json.loads(sf.read_text()) if sf.exists() else {}
    halt = False; fails = 0; seeded = 0; refreshed = 0
    for l in [l for l in locs if l["id"] not in store][:BATCH]:                       # 1) seed new locations
        try:
            store[l["id"]] = build_store(daily_series(f(l["lat"], l["lon"], START, end))); seeded += 1; fails = 0
            print(f"seeded {l['name']} ({seeded})", flush=True)
        except Stop as e: print("DAILY LIMIT:", e); halt = True; break
        except Exception as e:
            print("SKIP", l["name"], e); fails += 1
            if fails >= 3: print("3 failures in a row - stopping this run"); halt = True; break
        time.sleep(0 if DEMO else 1.5)
    if not halt:                                                                       # 2) refresh recent data
        for l in locs:
            st = store.get(l["id"])
            if not st or pd.Timestamp(st["d0"]) + pd.Timedelta(days=len(st["d"]) - 1) >= pd.Timestamp(end): continue
            try:
                if refresh(st, l, end, f) is None: del store[l["id"]]; print("gap -> will reseed", l["name"])
                else: refreshed += 1
            except Stop as e: print("DAILY LIMIT:", e); break
            except Exception as e: print("refresh failed", l["name"], str(e)[:100])
            time.sleep(0 if DEMO else 1)
    sf.write_text(json.dumps(store, separators=(",", ":")))
    ready = [l for l in locs if l["id"] in store]
    if not ready: sys.exit("No data yet - run again")
    upto = max(pd.Period(store[l["id"]]["m0"], "M") + len(store[l["id"]]["m"]) - 1 for l in ready).to_timestamp()
    pts, months = [], None
    for l in ready:
        pt, mo = derive(l, store[l["id"]], upto); pts.append(pt); months = months or mo
    through = max(pd.Timestamp(store[l["id"]]["d0"]) + pd.Timedelta(days=len(store[l["id"]]["d"]) - 1) for l in ready)
    out = dict(generated=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), demo=DEMO, data_through=str(through.date()),
               baseline=f"{B0}-{B1}", months=months, coverage=dict(loaded=len(ready), total=len(locs)),
               source="ECMWF ERA5 reanalysis via Open-Meteo Historical Weather API", points=pts)
    (DATA / "drought.json").write_text(json.dumps(out, separators=(",", ":")))
    briefing(pts, out["data_through"])
    print(f"seeded {seeded}, refreshed {refreshed}, coverage {len(ready)}/{len(locs)}, drought.json {(DATA/'drought.json').stat().st_size//1024} KB")

if __name__ == "__main__": main()
