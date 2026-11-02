import React, { useEffect, useRef } from 'react';
import Chart from 'chart.js/auto';
import { computeLinearTrend, formatMetric, getColor } from '../constants';
import { DroughtPoint } from '../types';

interface LocationInspectorProps {
  point: DroughtPoint | null;
  months: string[];
}

export const LocationInspector: React.FC<LocationInspectorProps> = ({ point, months }) => {
  const c1Ref = useRef<HTMLCanvasElement | null>(null);
  const c2Ref = useRef<HTMLCanvasElement | null>(null);
  const chart1Instance = useRef<Chart | null>(null);
  const chart2Instance = useRef<Chart | null>(null);

  useEffect(() => {
    if (!point || !c1Ref.current || !c2Ref.current) return;

    const years = point.annual.map((_, i) => point.y0 + i);
    const tr = computeLinearTrend(years, point.annual);
    const barColors = point.s3.map((v) => getColor(v, 'spi3'));

    if (chart1Instance.current) {
      chart1Instance.current.destroy();
    }
    if (chart2Instance.current) {
      chart2Instance.current.destroy();
    }

    chart1Instance.current = new Chart(c1Ref.current, {
      data: {
        labels: months,
        datasets: [
          {
            type: 'bar',
            label: 'SPI-3 (monthly)',
            data: point.s3,
            backgroundColor: barColors,
            borderRadius: 2,
            borderSkipped: false,
          },
          {
            type: 'line',
            label: 'SPI-12',
            data: point.s12,
            borderColor: '#0f172a',
            backgroundColor: '#0f172a',
            pointRadius: 0,
            borderWidth: 2,
            tension: 0.35,
            spanGaps: true,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        animation: { duration: 350 },
        plugins: {
          legend: {
            position: 'top',
            align: 'end',
            labels: {
              boxWidth: 10,
              boxHeight: 10,
              usePointStyle: false,
              font: { family: "'Plus Jakarta Sans', sans-serif", size: 11 },
              color: '#475569',
            },
          },
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: {
              maxTicksLimit: 7,
              font: { family: "'IBM Plex Mono', monospace", size: 10 },
              color: '#64748b',
            },
          },
          y: {
            min: -3,
            max: 3,
            grid: { color: '#f1f5f9' },
            ticks: {
              stepSize: 1,
              font: { family: "'IBM Plex Mono', monospace", size: 10 },
              color: '#64748b',
            },
          },
        },
      },
    });

    chart2Instance.current = new Chart(c2Ref.current, {
      data: {
        labels: years.map(String),
        datasets: [
          {
            type: 'bar',
            label: 'Annual precip (mm)',
            data: point.annual,
            backgroundColor: '#cbd5e1',
            hoverBackgroundColor: '#94a3b8',
            borderRadius: 2,
          },
          {
            type: 'line',
            label: 'Linear trend',
            data: tr.fit,
            borderColor: '#dc2626',
            backgroundColor: '#dc2626',
            borderWidth: 2,
            pointRadius: 0,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        animation: { duration: 350 },
        plugins: {
          legend: {
            position: 'top',
            align: 'end',
            labels: {
              boxWidth: 10,
              boxHeight: 10,
              font: { family: "'Plus Jakarta Sans', sans-serif", size: 11 },
              color: '#475569',
            },
          },
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: {
              maxTicksLimit: 7,
              font: { family: "'IBM Plex Mono', monospace", size: 10 },
              color: '#64748b',
            },
          },
          y: {
            grid: { color: '#f1f5f9' },
            ticks: {
              font: { family: "'IBM Plex Mono', monospace", size: 10 },
              color: '#64748b',
            },
          },
        },
      },
    });

    return () => {
      chart1Instance.current?.destroy();
      chart2Instance.current?.destroy();
    };
  }, [point, months]);

  if (!point) {
    return (
      <aside className="bg-white border border-slate-200 rounded-xl p-6 flex flex-col justify-center items-center text-center min-h-[420px]">
        <p className="text-sm font-medium text-slate-900">Select a monitoring location</p>
        <p className="text-xs text-slate-500 mt-1 max-w-xs">
          Click any marker on the map or select a row in the rankings table below to inspect multi-year SPI series and precipitation trends.
        </p>
      </aside>
    );
  }

  const years = point.annual.map((_, i) => point.y0 + i);
  const tr = computeLinearTrend(years, point.annual);
  const trendDecade = tr.b * 10;

  return (
    <aside className="bg-white border border-slate-200 rounded-xl p-5 sm:p-6 flex flex-col gap-5">
      <div>
        <div className="flex items-baseline justify-between gap-3">
          <h2 className="text-lg font-semibold tracking-tight text-slate-900">
            {point.name}, {point.country}
          </h2>
          <span className="font-mono text-xs text-slate-400 shrink-0">
            {point.lat.toFixed(2)}°, {point.lon.toFixed(2)}°
          </span>
        </div>
        <p className="text-xs text-slate-500 mt-1 leading-relaxed">
          {point.kind === 'region'
            ? 'Central Asian agricultural focus point'
            : 'Country-level grid sample'}
          {' · '}
          {point.subregion}
          {point.crop ? ` · ${point.crop}` : ''}
          {point.arid ? ' · Hyper-arid: SPI not reliable' : ''}
        </p>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-px bg-slate-200 border border-slate-200 rounded-lg overflow-hidden">
        <div className="bg-slate-50/70 p-3">
          <span className="block text-[11px] text-slate-500">SPI-3</span>
          <strong className="font-mono text-base font-semibold text-slate-900 mt-0.5 block">
            {formatMetric(point.spi3, 'spi3')}
          </strong>
        </div>
        <div className="bg-slate-50/70 p-3">
          <span className="block text-[11px] text-slate-500">SPI-12</span>
          <strong className="font-mono text-base font-semibold text-slate-900 mt-0.5 block">
            {formatMetric(point.spi12, 'spi12')}
          </strong>
        </div>
        <div className="bg-slate-50/70 p-3">
          <span className="block text-[11px] text-slate-500">30-day rain</span>
          <strong className="font-mono text-base font-semibold text-slate-900 mt-0.5 block">
            {formatMetric(point.anom30, 'anom30')}
          </strong>
        </div>
        <div className="bg-slate-50/70 p-3">
          <span className="block text-[11px] text-slate-500">Mean annual</span>
          <strong className="font-mono text-base font-semibold text-slate-900 mt-0.5 block">
            {point.mean} <span className="text-xs font-normal text-slate-500">mm</span>
          </strong>
        </div>
        <div className="bg-slate-50/70 p-3 col-span-2">
          <span className="block text-[11px] text-slate-500">Linear precipitation trend</span>
          <strong className="font-mono text-base font-semibold text-slate-900 mt-0.5 block">
            {trendDecade > 0 ? '+' : ''}
            {trendDecade.toFixed(1)}{' '}
            <span className="text-xs font-normal text-slate-500">mm / decade</span>
          </strong>
        </div>
      </div>

      <div>
        <div className="flex items-center justify-between mb-1.5">
          <h3 className="text-xs font-semibold text-slate-700">
            Standardized Precipitation Index (SPI-3 &amp; SPI-12)
          </h3>
        </div>
        <div className="h-[205px] relative">
          <canvas ref={c1Ref} />
        </div>
      </div>

      <div className="pt-3 border-t border-slate-100">
        <div className="flex items-center justify-between mb-1.5">
          <h3 className="text-xs font-semibold text-slate-700">
            Annual Precipitation &amp; Multi-Decadal Trend
          </h3>
        </div>
        <div className="h-[205px] relative">
          <canvas ref={c2Ref} />
        </div>
      </div>
    </aside>
  );
};
