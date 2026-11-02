import { DroughtPoint, IndicatorKey, SizeMode } from './types';

export const CARTO_KEY = 'cb1_4z5c_1_7e9005f3f1bcd5ce70511068';

export const COLS = [
  '#7F1D1D', // Extreme drought
  '#DC2626', // Severe drought
  '#EA580C', // Moderate drought
  '#D97706', // Mild dryness
  '#CBD5E1', // Near normal
  '#5EEAD4', // Mildly wet
  '#0D9488', // Wet
  '#115E59', // Very wet
];

export const COLS_BG = [
  'bg-red-900',
  'bg-red-600',
  'bg-orange-600',
  'bg-amber-600',
  'bg-slate-300',
  'bg-teal-300',
  'bg-teal-600',
  'bg-teal-800',
];

export const NA_COL = '#94A3B8';
export const NA_BG = 'bg-slate-400';

export const LAB = [
  'Extreme drought',
  'Severe drought',
  'Moderate drought',
  'Mild dryness',
  'Near normal',
  'Mildly wet',
  'Wet',
  'Very wet',
];

export const IND: Record<
  IndicatorKey,
  {
    l: string;
    short: string;
    t: number[];
    f: (v: number) => string;
  }
> = {
  spi3: {
    l: 'SPI-3 (3-month)',
    short: 'SPI-3',
    t: [-2, -1.5, -1, -0.5, 0.5, 1, 1.5],
    f: (v) => (v > 0 ? `+${v.toFixed(2)}` : v.toFixed(2)),
  },
  spi12: {
    l: 'SPI-12 (12-month)',
    short: 'SPI-12',
    t: [-2, -1.5, -1, -0.5, 0.5, 1, 1.5],
    f: (v) => (v > 0 ? `+${v.toFixed(2)}` : v.toFixed(2)),
  },
  anom30: {
    l: '30-day rain vs normal',
    short: '30-day Rain',
    t: [-80, -50, -25, -10, 10, 25, 50],
    f: (v) => `${v > 0 ? '+' : ''}${v.toFixed(0)}%`,
  },
};

export function getBinIndex(v: number, k: IndicatorKey): number {
  const thresholds = IND[k].t;
  let i = 0;
  while (i < thresholds.length && v > thresholds[i]) {
    i++;
  }
  return i;
}

export function getColor(v: number | null | undefined, k: IndicatorKey): string {
  if (v == null || Number.isNaN(v)) return NA_COL;
  return COLS[getBinIndex(v, k)];
}

export function getBgClass(v: number | null | undefined, k: IndicatorKey): string {
  if (v == null || Number.isNaN(v)) return NA_BG;
  return COLS_BG[getBinIndex(v, k)];
}

export function formatMetric(v: number | null | undefined, k: IndicatorKey): string {
  if (v == null || Number.isNaN(v)) return 'n/a';
  return IND[k].f(v);
}

export function computeRadius(p: DroughtPoint, k: IndicatorKey, sz: SizeMode): number {
  const v = p[k];
  if (sz === 'var') {
    return 5.5 + Math.min(p.cv || 0, 0.8) * 14;
  }
  if (v == null) return 5;
  return 5.5 + Math.min(Math.abs(k === 'anom30' ? v / 40 : v), 3) * 3.4;
}

export function computeLinearTrend(years: number[], values: number[]) {
  const n = years.length;
  if (!n) return { b: 0, fit: [] as number[] };
  const mx = years.reduce((s, v) => s + v, 0) / n;
  const my = values.reduce((s, v) => s + v, 0) / n;
  let nu = 0;
  let de = 0;
  years.forEach((v, i) => {
    nu += (v - mx) * (values[i] - my);
    de += (v - mx) ** 2;
  });
  const b = de === 0 ? 0 : nu / de;
  return {
    b,
    fit: years.map((v) => my + b * (v - mx)),
  };
}
