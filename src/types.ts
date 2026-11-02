export type IndicatorKey = 'spi3' | 'spi12' | 'anom30';
export type SizeMode = 'sev' | 'var';

export interface DroughtPoint {
  id: string;
  name: string;
  country: string;
  continent: string;
  subregion: string;
  kind: 'region' | 'country' | string;
  lat: number;
  lon: number;
  ag: boolean;
  crop?: string;
  arid?: boolean;
  cv?: number;
  spi3: number | null;
  spi12: number | null;
  anom30: number | null;
  mean: number;
  y0: number;
  annual: number[];
  s3: (number | null)[];
  s12: (number | null)[];
}

export interface DroughtDataset {
  data_through: string;
  generated: string;
  demo?: boolean;
  coverage: {
    loaded: number;
    total: number;
  };
  months: string[];
  points: DroughtPoint[];
}

export interface BriefingData {
  method: string;
  facts: {
    data_through: string;
  };
  text: string;
}
