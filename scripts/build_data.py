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

# Independent countries (name, ISO2, continent, subregion, lat, lon): REST Countries / mledoze dataset, centre points
COUNTRIES = [
 ('Afghanistan', 'AF', 'Asia', 'Southern Asia', 33, 65),('Albania', 'AL', 'Europe', 'Southeast Europe', 41, 20),
 ('Algeria', 'DZ', 'Africa', 'Northern Africa', 28, 3),('Andorra', 'AD', 'Europe', 'Southern Europe', 42.5, 1.5),
 ('Angola', 'AO', 'Africa', 'Middle Africa', -12.5, 18.5),('Antigua and Barbuda', 'AG', 'North America', 'Caribbean', 17.05, -61.8),
 ('Argentina', 'AR', 'South America', 'South America', -34, -64),('Armenia', 'AM', 'Asia', 'Western Asia', 40, 45),
 ('Australia', 'AU', 'Oceania', 'Australia and New Zealand', -27, 133),('Austria', 'AT', 'Europe', 'Central Europe', 47.33, 13.33),
 ('Azerbaijan', 'AZ', 'Asia', 'Western Asia', 40.5, 47.5),('Bahamas', 'BS', 'North America', 'Caribbean', 24.25, -76),
 ('Bahrain', 'BH', 'Asia', 'Western Asia', 26, 50.55),('Bangladesh', 'BD', 'Asia', 'Southern Asia', 24, 90),
 ('Barbados', 'BB', 'North America', 'Caribbean', 13.17, -59.53),('Belarus', 'BY', 'Europe', 'Eastern Europe', 53, 28),
 ('Belgium', 'BE', 'Europe', 'Western Europe', 50.83, 4),('Belize', 'BZ', 'North America', 'Central America', 17.25, -88.75),
 ('Benin', 'BJ', 'Africa', 'Western Africa', 9.5, 2.25),('Bhutan', 'BT', 'Asia', 'Southern Asia', 27.5, 90.5),
 ('Bolivia', 'BO', 'South America', 'South America', -17, -65),('Bosnia and Herzegovina', 'BA', 'Europe', 'Southeast Europe', 44, 18),
 ('Botswana', 'BW', 'Africa', 'Southern Africa', -22, 24),('Brazil', 'BR', 'South America', 'South America', -10, -55),
 ('Brunei', 'BN', 'Asia', 'South-Eastern Asia', 4.5, 114.67),('Bulgaria', 'BG', 'Europe', 'Southeast Europe', 43, 25),
 ('Burkina Faso', 'BF', 'Africa', 'Western Africa', 13, -2),('Burundi', 'BI', 'Africa', 'Eastern Africa', -3.5, 30),
 ('Cambodia', 'KH', 'Asia', 'South-Eastern Asia', 13, 105),('Cameroon', 'CM', 'Africa', 'Middle Africa', 6, 12),
 ('Canada', 'CA', 'North America', 'North America', 60, -95),('Cape Verde', 'CV', 'Africa', 'Western Africa', 16, -24),
 ('Central African Republic', 'CF', 'Africa', 'Middle Africa', 7, 21),('Chad', 'TD', 'Africa', 'Middle Africa', 15, 19),
 ('Chile', 'CL', 'South America', 'South America', -30, -71),('China', 'CN', 'Asia', 'Eastern Asia', 35, 105),
 ('Colombia', 'CO', 'South America', 'South America', 4, -72),('Comoros', 'KM', 'Africa', 'Eastern Africa', -12.17, 44.25),
 ('Congo', 'CG', 'Africa', 'Middle Africa', -1, 15),('Costa Rica', 'CR', 'North America', 'Central America', 10, -84),
 ('Croatia', 'HR', 'Europe', 'Southeast Europe', 45.17, 15.5),('Cuba', 'CU', 'North America', 'Caribbean', 21.5, -80),
 ('Cyprus', 'CY', 'Europe', 'Southern Europe', 35, 33),('Czechia', 'CZ', 'Europe', 'Central Europe', 49.75, 15.5),
 ('DR Congo', 'CD', 'Africa', 'Middle Africa', 0, 25),('Denmark', 'DK', 'Europe', 'Northern Europe', 56, 10),
 ('Djibouti', 'DJ', 'Africa', 'Eastern Africa', 11.5, 43),('Dominica', 'DM', 'North America', 'Caribbean', 15.42, -61.33),
 ('Dominican Republic', 'DO', 'North America', 'Caribbean', 19, -70.67),('Ecuador', 'EC', 'South America', 'South America', -2, -77.5),
 ('Egypt', 'EG', 'Africa', 'Northern Africa', 27, 30),('El Salvador', 'SV', 'North America', 'Central America', 13.83, -88.92),
 ('Equatorial Guinea', 'GQ', 'Africa', 'Middle Africa', 2, 10),('Eritrea', 'ER', 'Africa', 'Eastern Africa', 15, 39),
 ('Estonia', 'EE', 'Europe', 'Northern Europe', 59, 26),('Eswatini', 'SZ', 'Africa', 'Southern Africa', -26.5, 31.5),
 ('Ethiopia', 'ET', 'Africa', 'Eastern Africa', 8, 38),('Fiji', 'FJ', 'Oceania', 'Melanesia', -18, 175),
 ('Finland', 'FI', 'Europe', 'Northern Europe', 64, 26),('France', 'FR', 'Europe', 'Western Europe', 46, 2),
 ('Gabon', 'GA', 'Africa', 'Middle Africa', -1, 11.75),('Gambia', 'GM', 'Africa', 'Western Africa', 13.47, -16.57),
 ('Georgia', 'GE', 'Asia', 'Western Asia', 42, 43.5),('Germany', 'DE', 'Europe', 'Western Europe', 51, 9),
 ('Ghana', 'GH', 'Africa', 'Western Africa', 8, -2),('Greece', 'GR', 'Europe', 'Southern Europe', 39, 22),
 ('Grenada', 'GD', 'North America', 'Caribbean', 12.12, -61.67),('Guatemala', 'GT', 'North America', 'Central America', 15.5, -90.25),
 ('Guinea', 'GN', 'Africa', 'Western Africa', 11, -10),('Guinea-Bissau', 'GW', 'Africa', 'Western Africa', 12, -15),
 ('Guyana', 'GY', 'South America', 'South America', 5, -59),('Haiti', 'HT', 'North America', 'Caribbean', 19, -72.42),
 ('Honduras', 'HN', 'North America', 'Central America', 15, -86.5),('Hungary', 'HU', 'Europe', 'Central Europe', 47, 20),
 ('Iceland', 'IS', 'Europe', 'Northern Europe', 65, -18),('India', 'IN', 'Asia', 'Southern Asia', 20, 77),
 ('Indonesia', 'ID', 'Asia', 'South-Eastern Asia', -5, 120),('Iran', 'IR', 'Asia', 'Southern Asia', 32, 53),
 ('Iraq', 'IQ', 'Asia', 'Western Asia', 33, 44),('Ireland', 'IE', 'Europe', 'Northern Europe', 53, -8),
 ('Israel', 'IL', 'Asia', 'Western Asia', 31.47, 35.13),('Italy', 'IT', 'Europe', 'Southern Europe', 42.83, 12.83),
 ('Ivory Coast', 'CI', 'Africa', 'Western Africa', 8, -5),('Jamaica', 'JM', 'North America', 'Caribbean', 18.25, -77.5),
 ('Japan', 'JP', 'Asia', 'Eastern Asia', 36, 138),('Jordan', 'JO', 'Asia', 'Western Asia', 31, 36),
 ('Kazakhstan', 'KZ', 'Asia', 'Central Asia', 48, 68),('Kenya', 'KE', 'Africa', 'Eastern Africa', 1, 38),
 ('Kiribati', 'KI', 'Oceania', 'Micronesia', 1.42, 173),('Kuwait', 'KW', 'Asia', 'Western Asia', 29.5, 45.75),
 ('Kyrgyzstan', 'KG', 'Asia', 'Central Asia', 41, 75),('Laos', 'LA', 'Asia', 'South-Eastern Asia', 18, 105),
 ('Latvia', 'LV', 'Europe', 'Northern Europe', 57, 25),('Lebanon', 'LB', 'Asia', 'Western Asia', 33.83, 35.83),
 ('Lesotho', 'LS', 'Africa', 'Southern Africa', -29.5, 28.5),('Liberia', 'LR', 'Africa', 'Western Africa', 6.5, -9.5),
 ('Libya', 'LY', 'Africa', 'Northern Africa', 25, 17),('Liechtenstein', 'LI', 'Europe', 'Western Europe', 47.27, 9.53),
 ('Lithuania', 'LT', 'Europe', 'Northern Europe', 56, 24),('Luxembourg', 'LU', 'Europe', 'Western Europe', 49.75, 6.17),
 ('Madagascar', 'MG', 'Africa', 'Eastern Africa', -20, 47),('Malawi', 'MW', 'Africa', 'Eastern Africa', -13.5, 34),
 ('Malaysia', 'MY', 'Asia', 'South-Eastern Asia', 2.5, 112.5),('Maldives', 'MV', 'Asia', 'Southern Asia', 3.25, 73),
 ('Mali', 'ML', 'Africa', 'Western Africa', 17, -4),('Malta', 'MT', 'Europe', 'Southern Europe', 35.83, 14.58),
 ('Marshall Islands', 'MH', 'Oceania', 'Micronesia', 9, 168),('Mauritania', 'MR', 'Africa', 'Western Africa', 20, -12),
 ('Mauritius', 'MU', 'Africa', 'Eastern Africa', -20.28, 57.55),('Mexico', 'MX', 'North America', 'North America', 23, -102),
 ('Micronesia', 'FM', 'Oceania', 'Micronesia', 6.92, 158.25),('Moldova', 'MD', 'Europe', 'Eastern Europe', 47, 29),
 ('Monaco', 'MC', 'Europe', 'Western Europe', 43.73, 7.4),('Mongolia', 'MN', 'Asia', 'Eastern Asia', 46, 105),
 ('Montenegro', 'ME', 'Europe', 'Southeast Europe', 42.5, 19.3),('Morocco', 'MA', 'Africa', 'Northern Africa', 32, -5),
 ('Mozambique', 'MZ', 'Africa', 'Eastern Africa', -18.25, 35),('Myanmar', 'MM', 'Asia', 'South-Eastern Asia', 22, 98),
 ('Namibia', 'NA', 'Africa', 'Southern Africa', -22, 17),('Nauru', 'NR', 'Oceania', 'Micronesia', -0.53, 166.92),
 ('Nepal', 'NP', 'Asia', 'Southern Asia', 28, 84),('Netherlands', 'NL', 'Europe', 'Western Europe', 52.5, 5.75),
 ('New Zealand', 'NZ', 'Oceania', 'Australia and New Zealand', -41, 174),('Nicaragua', 'NI', 'North America', 'Central America', 13, -85),
 ('Niger', 'NE', 'Africa', 'Western Africa', 16, 8),('Nigeria', 'NG', 'Africa', 'Western Africa', 10, 8),
 ('North Korea', 'KP', 'Asia', 'Eastern Asia', 40, 127),('North Macedonia', 'MK', 'Europe', 'Southeast Europe', 41.83, 22),
 ('Norway', 'NO', 'Europe', 'Northern Europe', 62, 10),('Oman', 'OM', 'Asia', 'Western Asia', 21, 57),
 ('Pakistan', 'PK', 'Asia', 'Southern Asia', 30, 70),('Palau', 'PW', 'Oceania', 'Micronesia', 7.5, 134.5),
 ('Panama', 'PA', 'North America', 'Central America', 9, -80),('Papua New Guinea', 'PG', 'Oceania', 'Melanesia', -6, 147),
 ('Paraguay', 'PY', 'South America', 'South America', -23, -58),('Peru', 'PE', 'South America', 'South America', -10, -76),
 ('Philippines', 'PH', 'Asia', 'South-Eastern Asia', 13, 122),('Poland', 'PL', 'Europe', 'Central Europe', 52, 20),
 ('Portugal', 'PT', 'Europe', 'Southern Europe', 39.5, -8),('Qatar', 'QA', 'Asia', 'Western Asia', 25.5, 51.25),
 ('Romania', 'RO', 'Europe', 'Southeast Europe', 46, 25),('Russia', 'RU', 'Europe', 'Eastern Europe', 60, 100),
 ('Rwanda', 'RW', 'Africa', 'Eastern Africa', -2, 30),('Saint Kitts and Nevis', 'KN', 'North America', 'Caribbean', 17.33, -62.75),
 ('Saint Lucia', 'LC', 'North America', 'Caribbean', 13.88, -60.97),
 ('Saint Vincent and the Grenadines', 'VC', 'North America', 'Caribbean', 13.25, -61.2),('Samoa', 'WS', 'Oceania', 'Polynesia', -13.58, -172.33),
 ('San Marino', 'SM', 'Europe', 'Southern Europe', 43.77, 12.42),('Saudi Arabia', 'SA', 'Asia', 'Western Asia', 25, 45),
 ('Senegal', 'SN', 'Africa', 'Western Africa', 14, -14),('Serbia', 'RS', 'Europe', 'Southeast Europe', 44, 21),
 ('Seychelles', 'SC', 'Africa', 'Eastern Africa', -4.58, 55.67),('Sierra Leone', 'SL', 'Africa', 'Western Africa', 8.5, -11.5),
 ('Singapore', 'SG', 'Asia', 'South-Eastern Asia', 1.37, 103.8),('Slovakia', 'SK', 'Europe', 'Central Europe', 48.67, 19.5),
 ('Slovenia', 'SI', 'Europe', 'Central Europe', 46.12, 14.82),('Solomon Islands', 'SB', 'Oceania', 'Melanesia', -8, 159),
 ('Somalia', 'SO', 'Africa', 'Eastern Africa', 10, 49),('South Africa', 'ZA', 'Africa', 'Southern Africa', -29, 24),
 ('South Korea', 'KR', 'Asia', 'Eastern Asia', 37, 127.5),('South Sudan', 'SS', 'Africa', 'Middle Africa', 7, 30),
 ('Spain', 'ES', 'Europe', 'Southern Europe', 40, -4),('Sri Lanka', 'LK', 'Asia', 'Southern Asia', 7, 81),
 ('Sudan', 'SD', 'Africa', 'Northern Africa', 15, 30),('Suriname', 'SR', 'South America', 'South America', 4, -56),
 ('Sweden', 'SE', 'Europe', 'Northern Europe', 62, 15),('Switzerland', 'CH', 'Europe', 'Western Europe', 47, 8),
 ('Syria', 'SY', 'Asia', 'Western Asia', 35, 38),('São Tomé and Príncipe', 'ST', 'Africa', 'Middle Africa', 1, 7),
 ('Tajikistan', 'TJ', 'Asia', 'Central Asia', 39, 71),('Tanzania', 'TZ', 'Africa', 'Eastern Africa', -6, 35),
 ('Thailand', 'TH', 'Asia', 'South-Eastern Asia', 15, 100),('Timor-Leste', 'TL', 'Asia', 'South-Eastern Asia', -8.83, 125.92),
 ('Togo', 'TG', 'Africa', 'Western Africa', 8, 1.17),('Tonga', 'TO', 'Oceania', 'Polynesia', -20, -175),
 ('Trinidad and Tobago', 'TT', 'North America', 'Caribbean', 11, -61),('Tunisia', 'TN', 'Africa', 'Northern Africa', 34, 9),
 ('Turkmenistan', 'TM', 'Asia', 'Central Asia', 40, 60),('Tuvalu', 'TV', 'Oceania', 'Polynesia', -8, 178),
 ('Türkiye', 'TR', 'Asia', 'Western Asia', 39, 35),('Uganda', 'UG', 'Africa', 'Eastern Africa', 1, 32),
 ('Ukraine', 'UA', 'Europe', 'Eastern Europe', 49, 32),('United Arab Emirates', 'AE', 'Asia', 'Western Asia', 24, 54),
 ('United Kingdom', 'GB', 'Europe', 'Northern Europe', 54, -2),('United States', 'US', 'North America', 'North America', 38, -97),
 ('Uruguay', 'UY', 'South America', 'South America', -33, -56),('Uzbekistan', 'UZ', 'Asia', 'Central Asia', 41, 64),
 ('Vanuatu', 'VU', 'Oceania', 'Melanesia', -16, 167),('Vatican City', 'VA', 'Europe', 'Southern Europe', 41.9, 12.45),
 ('Venezuela', 'VE', 'South America', 'South America', 8, -66),('Vietnam', 'VN', 'Asia', 'South-Eastern Asia', 16.17, 107.83),
 ('Yemen', 'YE', 'Asia', 'Western Asia', 15, 48),('Zambia', 'ZM', 'Africa', 'Eastern Africa', -15, 30),
 ('Zimbabwe', 'ZW', 'Africa', 'Eastern Africa', -20, 30),
]

def countries():
    return [dict(id="c-" + i.lower(), name=n, country=n, iso=i, continent=ct, subregion=sr, lat=la, lon=lo, kind="country", crop="")
            for n, i, ct, sr, la, lo in (COUNTRIES if not DEMO else COUNTRIES[:6])]

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
