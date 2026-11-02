import { useEffect, useMemo, useState } from 'react';
import { Download, RotateCcw, Search } from 'lucide-react';
import { LocationInspector } from './components/LocationInspector';
import { MapPanel } from './components/MapPanel';
import {
  IND,
  LAB,
  formatMetric,
  getBgClass,
  getBinIndex,
} from './constants';
import {
  BriefingData,
  DroughtDataset,
  DroughtPoint,
  IndicatorKey,
  SizeMode,
} from './types';

function uniqSorted(items: string[]): string[] {
  return Array.from(new Set(items.filter(Boolean))).sort();
}

export default function App() {
  const [dataset, setDataset] = useState<DroughtDataset | null>(null);
  const [briefing, setBriefing] = useState<BriefingData | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [indicator, setIndicator] = useState<IndicatorKey>('spi3');
  const [continent, setContinent] = useState('');
  const [subregion, setSubregion] = useState('');
  const [country, setCountry] = useState('');
  const [query, setQuery] = useState('');
  const [agOnly, setAgOnly] = useState(false);
  const [sizeMode, setSizeMode] = useState<SizeMode>('sev');
  const [limit, setLimit] = useState(25);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [fitTrigger, setFitTrigger] = useState(0);

  useEffect(() => {
    fetch('data/drought.json', { cache: 'no-cache' })
      .then((r) => {
        if (!r.ok) throw new Error('Failed to load dataset');
        return r.json();
      })
      .then((d: DroughtDataset) => {
        setDataset(d);
        const driest =
          [...d.points]
            .filter((p) => p.spi3 != null)
            .sort((a, b) => (a.spi3 ?? 99) - (b.spi3 ?? 99))[0] || d.points[0];
        if (driest) setSelectedId(driest.id);
        setFitTrigger((n) => n + 1);
      })
      .catch(() => {
        setError('No data yet — run the “Update data” workflow');
      });

    fetch('data/briefing.json', { cache: 'no-cache' })
      .then((r) => (r.ok ? r.json() : null))
      .then((b: BriefingData | null) => {
        if (b && b.text) setBriefing(b);
      })
      .catch(() => {});
  }, []);

  const allPoints = dataset?.points ?? [];

  const continentOptions = useMemo(
    () => uniqSorted(allPoints.map((p) => p.continent)),
    [allPoints]
  );

  const subregionOptions = useMemo(
    () =>
      uniqSorted(
        allPoints
          .filter((p) => !continent || p.continent === continent)
          .map((p) => p.subregion)
      ),
    [allPoints, continent]
  );

  const countryOptions = useMemo(
    () =>
      uniqSorted(
        allPoints
          .filter(
            (p) =>
              (!continent || p.continent === continent) &&
              (!subregion || p.subregion === subregion)
          )
          .map((p) => p.country)
      ),
    [allPoints, continent, subregion]
  );

  const visiblePoints = useMemo(() => {
    const q = query.trim().toLowerCase();
    return allPoints.filter(
      (p) =>
        (!continent || p.continent === continent) &&
        (!subregion || p.subregion === subregion) &&
        (!country || p.country === country) &&
        (!agOnly || p.ag) &&
        (!q || `${p.name} ${p.country} ${p.crop ?? ''}`.toLowerCase().includes(q))
    );
  }, [allPoints, continent, subregion, country, agOnly, query]);

  const sortedRows = useMemo(() => {
    return [...visiblePoints].sort(
      (a, b) => (a[indicator] ?? 999) - (b[indicator] ?? 999)
    );
  }, [visiblePoints, indicator]);

  const selectedPoint: DroughtPoint | null = useMemo(() => {
    if (!allPoints.length) return null;
    return allPoints.find((p) => p.id === selectedId) ?? visiblePoints[0] ?? null;
  }, [allPoints, visiblePoints, selectedId]);

  const kpiStats = useMemo(() => {
    const valid = visiblePoints.filter((p) => p.spi3 != null);
    const inDrought = valid.filter((p) => (p.spi3 ?? 0) <= -1);
    const agStress = valid.filter((p) => p.ag && (p.spi3 ?? 0) <= -1);
    const meanSpi3 =
      valid.length > 0
        ? valid.reduce((sum, p) => sum + (p.spi3 ?? 0), 0) / valid.length
        : null;
    const driest = [...valid].sort((a, b) => (a.spi3 ?? 99) - (b.spi3 ?? 99))[0];
    return {
      total: visiblePoints.length,
      validCount: valid.length,
      inDroughtCount: inDrought.length,
      agStressCount: agStress.length,
      meanSpi3,
      driest,
    };
  }, [visiblePoints]);

  const hasFilters = Boolean(continent || subregion || country || query.trim() || agOnly);

  const resetFilters = () => {
    setContinent('');
    setSubregion('');
    setCountry('');
    setQuery('');
    setAgOnly(false);
    setLimit(25);
    setFitTrigger((n) => n + 1);
  };

  const handleExportCsv = () => {
    if (!sortedRows.length) return;
    const headers = [
      'ID',
      'Location',
      'Country',
      'Continent',
      'Subregion',
      'Lat',
      'Lon',
      'Agricultural_Focus',
      'Crop',
      'SPI_3',
      'SPI_12',
      'Rain_30d_Anomaly_Pct',
      'Mean_Annual_mm',
    ];
    const lines = sortedRows.map((p) =>
      [
        p.id,
        `"${p.name.replace(/"/g, '""')}"`,
        `"${p.country.replace(/"/g, '""')}"`,
        `"${p.continent}"`,
        `"${p.subregion}"`,
        p.lat,
        p.lon,
        p.ag ? 'Yes' : 'No',
        `"${(p.crop || '').replace(/"/g, '""')}"`,
        p.spi3 ?? '',
        p.spi12 ?? '',
        p.anom30 ?? '',
        p.mean,
      ].join(',')
    );
    const blob = new Blob([[headers.join(','), ...lines].join('\n')], {
      type: 'text/csv;charset=utf-8;',
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `aralwatch-drought-${dataset?.data_through || 'export'}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-slate-900">
      {/* Top Bar Contract: 3 Zones (Brand — Nav Links — 1 Primary Action) */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-30">
        <div className="max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between gap-8">
          <a
            href="#overview"
            className="text-lg font-bold tracking-tight text-slate-900 whitespace-nowrap shrink-0"
          >
            Aral<span className="text-red-700">Watch</span>
          </a>

          <nav className="hidden md:flex items-center gap-6 text-sm font-medium text-slate-600">
            <a
              href="#overview"
              className="hover:text-slate-900 transition-colors whitespace-nowrap shrink-0"
            >
              Overview
            </a>
            {briefing && (
              <a
                href="#briefing"
                className="hover:text-slate-900 transition-colors whitespace-nowrap shrink-0"
              >
                Briefing
              </a>
            )}
            <a
              href="#map-workspace"
              className="hover:text-slate-900 transition-colors whitespace-nowrap shrink-0"
            >
              Global Map
            </a>
            <a
              href="#rankings"
              className="hover:text-slate-900 transition-colors whitespace-nowrap shrink-0"
            >
              Rankings
            </a>
            <a
              href="#methodology"
              className="hover:text-slate-900 transition-colors whitespace-nowrap shrink-0"
            >
              Methodology
            </a>
          </nav>

          <div className="flex items-center shrink-0">
            <button
              type="button"
              onClick={handleExportCsv}
              disabled={!sortedRows.length}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-medium text-white bg-slate-900 rounded-lg hover:bg-slate-800 disabled:opacity-40 transition-colors whitespace-nowrap shrink-0 cursor-pointer"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Export CSV</span>
            </button>
          </div>
        </div>
      </header>

      {/* Optional Demo / Coverage Banners */}
      {dataset?.demo && (
        <div className="bg-amber-50 border-b border-amber-200 px-4 py-2 text-center text-xs font-medium text-amber-900">
          DEMO DATA — synthetic dataset for local testing only
        </div>
      )}
      {dataset && dataset.coverage.loaded < dataset.coverage.total && (
        <div className="bg-slate-900 px-4 py-2 text-center text-xs font-medium text-slate-200">
          Global backfill in progress: {dataset.coverage.loaded} of {dataset.coverage.total}{' '}
          locations loaded — more appear after each automated update.
        </div>
      )}

      <div className="max-w-[1440px] w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8 space-y-6 flex-1">
        {/* Workspace Context Header */}
        <section id="overview" className="flex flex-col md:flex-row md:items-end justify-between gap-3">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">
              Global Drought &amp; Rainfall Intelligence
            </h1>
            <p className="text-sm text-slate-600 mt-1">
              ECMWF ERA5 reanalysis climate telemetry with Central Asian agricultural basin focus
            </p>
          </div>
          <div className="text-xs text-slate-500 font-mono">
            {error ? (
              <span className="text-red-600">{error}</span>
            ) : dataset ? (
              <span>
                Data through {dataset.data_through} · Refreshed {dataset.generated.slice(0, 10)}
              </span>
            ) : (
              <span>Loading climate reanalysis…</span>
            )}
          </div>
        </section>

        {/* KPI Summary Strip */}
        <section
          aria-label="Key climate indicators"
          className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 sm:gap-4"
        >
          <div className="bg-white border border-slate-200 rounded-xl p-4 sm:p-5">
            <span className="block text-xs text-slate-500">Locations in selection</span>
            <strong className="block font-mono text-2xl font-semibold text-slate-900 mt-1">
              {dataset ? kpiStats.total : '—'}
            </strong>
          </div>

          <div className="bg-white border border-slate-200 rounded-xl p-4 sm:p-5">
            <span className="block text-xs text-slate-500">In drought (SPI-3 ≤ −1.0)</span>
            <strong className="block font-mono text-2xl font-semibold text-red-600 mt-1">
              {dataset ? `${kpiStats.inDroughtCount} / ${kpiStats.validCount}` : '—'}
            </strong>
          </div>

          <div className="bg-white border border-slate-200 rounded-xl p-4 sm:p-5">
            <span className="block text-xs text-slate-500">Agricultural areas under stress</span>
            <strong className="block font-mono text-2xl font-semibold text-amber-600 mt-1">
              {dataset ? kpiStats.agStressCount : '—'}
            </strong>
          </div>

          <div className="bg-white border border-slate-200 rounded-xl p-4 sm:p-5">
            <span className="block text-xs text-slate-500">Mean SPI-3 index</span>
            <strong className="block font-mono text-2xl font-semibold text-slate-900 mt-1">
              {dataset
                ? kpiStats.meanSpi3 != null
                  ? formatMetric(kpiStats.meanSpi3, 'spi3')
                  : 'n/a'
                : '—'}
            </strong>
          </div>

          <div className="bg-white border border-slate-200 rounded-xl p-4 sm:p-5">
            <span className="block text-xs text-slate-500">Driest location right now</span>
            <strong className="block text-lg font-semibold text-slate-900 mt-1 truncate">
              {kpiStats.driest ? kpiStats.driest.name : '—'}
            </strong>
            {kpiStats.driest && (
              <span className="block font-mono text-xs text-red-700 mt-0.5">
                SPI-3 {formatMetric(kpiStats.driest.spi3, 'spi3')} · {kpiStats.driest.country}
              </span>
            )}
          </div>
        </section>

        {/* Situation Briefing */}
        {briefing && (
          <section
            id="briefing"
            className="bg-white border border-slate-200 rounded-xl p-5 sm:p-6"
          >
            <div className="flex flex-wrap items-baseline justify-between gap-2 mb-3">
              <h2 className="text-base font-semibold text-slate-900">Situation briefing</h2>
              <div className="text-xs text-slate-500">
                <span>
                  {briefing.method === 'claude'
                    ? 'Synthesized from computed indicators'
                    : 'Auto-generated from computed indicators'}
                </span>
                <span aria-hidden="true"> · </span>
                <span className="font-mono">Data through {briefing.facts.data_through}</span>
              </div>
            </div>
            <div className="space-y-2.5 text-sm text-slate-700 leading-relaxed max-w-4xl">
              {briefing.text.split(/\n\n+/).map((para, idx) => (
                <p key={idx}>{para}</p>
              ))}
            </div>
          </section>
        )}

        {/* Main Asymmetric Split Workspace: Map + Location Telemetry Inspector */}
        <main
          id="map-workspace"
          className="grid grid-cols-1 xl:grid-cols-12 gap-6 items-start"
        >
          {/* Map & Filter Controls Card */}
          <div className="xl:col-span-7 bg-white border border-slate-200 rounded-xl p-4 sm:p-5 space-y-4">
            {/* Toolbar */}
            <div className="flex flex-col gap-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                {/* Segmented Indicator Selector */}
                <div
                  role="group"
                  aria-label="Climate indicator"
                  className="inline-flex items-center p-1 bg-slate-100 rounded-lg border border-slate-200/70"
                >
                  {(Object.keys(IND) as IndicatorKey[]).map((k) => {
                    const active = indicator === k;
                    return (
                      <button
                        key={k}
                        type="button"
                        onClick={() => setIndicator(k)}
                        className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors whitespace-nowrap shrink-0 cursor-pointer ${
                          active
                            ? 'bg-white text-slate-900 shadow-xs'
                            : 'text-slate-600 hover:text-slate-900'
                        }`}
                      >
                        {IND[k].short}
                      </button>
                    );
                  })}
                </div>

                {/* Search Input */}
                <div className="relative flex-1 min-w-[180px] sm:max-w-[240px]">
                  <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                  <input
                    type="search"
                    value={query}
                    onChange={(e) => {
                      setQuery(e.target.value);
                      setLimit(25);
                      setFitTrigger((n) => n + 1);
                    }}
                    placeholder="Search location or crop…"
                    className="w-full pl-8 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg text-slate-900 placeholder:text-slate-400 focus:outline-none focus:bg-white focus:border-slate-400 transition-colors"
                  />
                </div>
              </div>

              {/* Geographic & Sizing Filters */}
              <div className="flex flex-wrap items-center gap-2">
                <select
                  aria-label="Filter by continent"
                  value={continent}
                  onChange={(e) => {
                    setContinent(e.target.value);
                    setSubregion('');
                    setCountry('');
                    setLimit(25);
                    setFitTrigger((n) => n + 1);
                  }}
                  className="px-2.5 py-1.5 text-xs bg-white border border-slate-200 rounded-lg text-slate-700 focus:outline-none focus:border-slate-400"
                >
                  <option value="">All continents</option>
                  {continentOptions.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>

                <select
                  aria-label="Filter by subregion"
                  value={subregion}
                  onChange={(e) => {
                    setSubregion(e.target.value);
                    setCountry('');
                    setLimit(25);
                    setFitTrigger((n) => n + 1);
                  }}
                  className="px-2.5 py-1.5 text-xs bg-white border border-slate-200 rounded-lg text-slate-700 focus:outline-none focus:border-slate-400"
                >
                  <option value="">All subregions</option>
                  {subregionOptions.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>

                <select
                  aria-label="Filter by country"
                  value={country}
                  onChange={(e) => {
                    setCountry(e.target.value);
                    setLimit(25);
                    setFitTrigger((n) => n + 1);
                  }}
                  className="px-2.5 py-1.5 text-xs bg-white border border-slate-200 rounded-lg text-slate-700 focus:outline-none focus:border-slate-400"
                >
                  <option value="">All countries</option>
                  {countryOptions.map((y) => (
                    <option key={y} value={y}>
                      {y}
                    </option>
                  ))}
                </select>

                <select
                  aria-label="Circle size metric"
                  value={sizeMode}
                  onChange={(e) => setSizeMode(e.target.value as SizeMode)}
                  className="px-2.5 py-1.5 text-xs bg-white border border-slate-200 rounded-lg text-slate-700 focus:outline-none focus:border-slate-400"
                >
                  <option value="sev">Size: Anomaly severity</option>
                  <option value="var">Size: Rainfall variability</option>
                </select>

                <label className="inline-flex items-center gap-1.5 text-xs text-slate-700 px-2 py-1.5 select-none cursor-pointer">
                  <input
                    type="checkbox"
                    checked={agOnly}
                    onChange={(e) => {
                      setAgOnly(e.target.checked);
                      setLimit(25);
                      setFitTrigger((n) => n + 1);
                    }}
                    className="rounded border-slate-300 text-slate-900 focus:ring-slate-500"
                  />
                  <span className="whitespace-nowrap">Agricultural focus only</span>
                </label>

                {hasFilters && (
                  <button
                    type="button"
                    onClick={resetFilters}
                    className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-slate-600 hover:text-slate-900 bg-slate-100 hover:bg-slate-200/70 rounded-lg transition-colors whitespace-nowrap cursor-pointer"
                  >
                    <RotateCcw className="w-3 h-3" />
                    <span>Reset</span>
                  </button>
                )}
              </div>
            </div>

            <MapPanel
              points={visiblePoints}
              indicator={indicator}
              sizeMode={sizeMode}
              selected={selectedPoint}
              onSelect={(p) => setSelectedId(p.id)}
              hasActiveBoundsFilter={hasFilters}
              fitTrigger={fitTrigger}
            />
          </div>

          {/* Right Inspector Column */}
          <div className="xl:col-span-5 xl:sticky xl:top-20">
            <LocationInspector point={selectedPoint} months={dataset?.months ?? []} />
          </div>
        </main>

        {/* Ranked Locations Data Grid */}
        <section
          id="rankings"
          className="bg-white border border-slate-200 rounded-xl overflow-hidden"
        >
          <div className="px-5 py-4 border-b border-slate-200 flex flex-wrap items-baseline justify-between gap-2">
            <div>
              <h2 className="text-base font-semibold text-slate-900">
                Locations ranked by current dryness ({IND[indicator].short})
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Click any row to inspect historical SPI series and precipitation trends
              </p>
            </div>
            <span className="text-xs font-mono text-slate-500">
              Showing {Math.min(sortedRows.length, limit)} of {sortedRows.length} locations
            </span>
          </div>

          {sortedRows.length === 0 ? (
            <div className="p-10 text-center">
              <p className="text-sm font-medium text-slate-900">
                No monitoring locations match your active filters
              </p>
              <p className="text-xs text-slate-500 mt-1">
                Try clearing a geographic filter or search term to view global ERA5 samples.
              </p>
              {hasFilters && (
                <button
                  type="button"
                  onClick={resetFilters}
                  className="mt-4 px-4 py-2 text-xs font-medium text-white bg-slate-900 rounded-lg hover:bg-slate-800 transition-colors cursor-pointer"
                >
                  Reset filters
                </button>
              )}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-sm">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50/70 text-xs font-medium text-slate-500">
                    <th className="py-3 px-4">Location</th>
                    <th className="py-3 px-4">Country</th>
                    <th className="py-3 px-4">Agricultural focus</th>
                    <th className="py-3 px-4 text-right">SPI-3</th>
                    <th className="py-3 px-4 text-right">SPI-12</th>
                    <th className="py-3 px-4 text-right">30-day rain</th>
                    <th className="py-3 px-4">Condition</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {sortedRows.slice(0, limit).map((p) => {
                    const isNull = p.spi3 == null;
                    const bin = isNull ? -1 : getBinIndex(p.spi3 as number, 'spi3');
                    const swatchBg = getBgClass(p.spi3, 'spi3');
                    const isSelected = selectedPoint?.id === p.id;

                    return (
                      <tr
                        key={p.id}
                        onClick={() => {
                          setSelectedId(p.id);
                          window.scrollTo({ top: 0, behavior: 'smooth' });
                        }}
                        className={`cursor-pointer transition-colors ${
                          isSelected
                            ? 'bg-sky-50/80 hover:bg-sky-50'
                            : 'hover:bg-slate-50/90'
                        }`}
                      >
                        <td className="py-2.5 px-4 font-medium text-slate-900 whitespace-nowrap">
                          {p.name}
                        </td>
                        <td className="py-2.5 px-4 text-slate-600 whitespace-nowrap">
                          {p.country}
                        </td>
                        <td className="py-2.5 px-4 text-slate-500 text-xs max-w-[240px] truncate">
                          {p.crop || '—'}
                        </td>
                        <td className="py-2.5 px-4 text-right font-mono text-xs font-medium text-slate-900 whitespace-nowrap">
                          {formatMetric(p.spi3, 'spi3')}
                        </td>
                        <td className="py-2.5 px-4 text-right font-mono text-xs text-slate-700 whitespace-nowrap">
                          {formatMetric(p.spi12, 'spi12')}
                        </td>
                        <td className="py-2.5 px-4 text-right font-mono text-xs text-slate-700 whitespace-nowrap">
                          {formatMetric(p.anom30, 'anom30')}
                        </td>
                        <td className="py-2.5 px-4 whitespace-nowrap text-xs text-slate-700">
                          <span className="inline-flex items-center gap-2">
                            <span
                              className={`w-2.5 h-2.5 rounded-xs shrink-0 border border-slate-900/15 ${swatchBg}`}
                            />
                            <span>{isNull ? 'n/a (hyper-arid)' : LAB[bin]}</span>
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {sortedRows.length > limit && (
            <div className="p-4 border-t border-slate-100 text-center">
              <button
                type="button"
                onClick={() => setLimit((l) => l + 50)}
                className="px-4 py-2 text-xs font-medium text-slate-700 bg-slate-100 hover:bg-slate-200/80 rounded-lg transition-colors cursor-pointer"
              >
                Show more ({sortedRows.length - limit} remaining)
              </button>
            </div>
          )}
        </section>
      </div>

      {/* Methodology Footer */}
      <footer
        id="methodology"
        className="border-t border-slate-200 bg-white mt-8 py-6 px-4 sm:px-6 lg:px-8"
      >
        <div className="max-w-[1440px] mx-auto text-xs text-slate-500 leading-relaxed">
          <strong className="font-semibold text-slate-700">Method.</strong> Daily precipitation
          from ECMWF ERA5 reanalysis (via the Open-Meteo Historical Weather API) aggregated to
          months. SPI = Standardized Precipitation Index (gamma fit per calendar month,
          1991–2020 baseline); ≤ −1.0 indicates moderate drought or worse. SPI-3 = last 3 months,
          SPI-12 = last 12 months. “30-day rain” compares the latest 30 days with the 1991–2020
          average for the same dates. Each marker represents one ERA5 grid-cell sample (country
          centre point, or a Central Asian agricultural focus point), not an area average — large
          countries are only roughly represented. SPI is hidden (n/a) in hyper-arid places
          (&lt;100 mm/year). ERA5 lags real time by about 5–7 days. The situation briefing is
          generated strictly from the computed indicators; verify against the table. Data
          refreshed automatically by GitHub Actions. Contains modified Copernicus Climate Change
          Service information. Map © OpenStreetMap © CARTO.
        </div>
      </footer>
    </div>
  );
}
