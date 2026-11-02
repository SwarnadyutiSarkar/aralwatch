import React, { useEffect, useRef } from 'react';
import L from 'leaflet';
import {
  CARTO_KEY,
  COLS_BG,
  IND,
  LAB,
  NA_BG,
  computeRadius,
  formatMetric,
  getColor,
} from '../constants';
import { DroughtPoint, IndicatorKey, SizeMode } from '../types';

interface MapPanelProps {
  points: DroughtPoint[];
  indicator: IndicatorKey;
  sizeMode: SizeMode;
  selected: DroughtPoint | null;
  onSelect: (p: DroughtPoint) => void;
  hasActiveBoundsFilter: boolean;
  fitTrigger: number;
}

export const MapPanel: React.FC<MapPanelProps> = ({
  points,
  indicator,
  sizeMode,
  selected,
  onSelect,
  hasActiveBoundsFilter,
  fitTrigger,
}) => {
  const mapElRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const layerRef = useRef<L.LayerGroup | null>(null);

  useEffect(() => {
    if (!mapElRef.current || mapRef.current) return;

    const map = L.map(mapElRef.current, {
      minZoom: 2,
      worldCopyJump: true,
      zoomControl: true,
    }).setView([32, 48], 2);

    L.tileLayer(
      `https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png?key=${CARTO_KEY}`,
      {
        attribution: '&copy; OpenStreetMap &copy; CARTO',
        maxZoom: 12,
      }
    ).addTo(map);

    layerRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
      layerRef.current = null;
    };
  }, []);

  useEffect(() => {
    const layer = layerRef.current;
    if (!layer) return;

    layer.clearLayers();

    points.forEach((p) => {
      const r = computeRadius(p, indicator, sizeMode);
      const marker = L.circleMarker([p.lat, p.lon], {
        radius: r,
        fillColor: getColor(p[indicator], indicator),
        color: '#0f172a',
        weight: p.ag ? 2 : 1,
        fillOpacity: 0.9,
      });

      marker.bindTooltip(
        `<div class="tt-title">${p.name}, ${p.country}</div>` +
          `<div class="tt-meta">${IND[indicator].short}: ${formatMetric(p[indicator], indicator)}${p.ag ? ' · Ag Focus' : ''}</div>`,
        { direction: 'top', offset: [0, -4] }
      );

      marker.on('click', () => onSelect(p));
      marker.addTo(layer);

      if (selected && p.id === selected.id) {
        L.circleMarker([p.lat, p.lon], {
          radius: r + 5,
          fill: false,
          color: '#0f172a',
          weight: 2,
          dashArray: '4 4',
        }).addTo(layer);
      }
    });
  }, [points, indicator, sizeMode, selected, onSelect]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !points.length) return;

    if (hasActiveBoundsFilter) {
      const bounds = L.latLngBounds(points.map((p) => [p.lat, p.lon] as [number, number]));
      map.fitBounds(bounds, { padding: [32, 32], maxZoom: 6 });
    } else {
      map.setView([32, 48], 2);
    }
  }, [fitTrigger]);

  return (
    <div>
      <div
        ref={mapElRef}
        className="h-[460px] sm:h-[540px] w-full rounded-lg border border-slate-200 overflow-hidden z-0"
      />
      <div className="mt-4 pt-3 border-t border-slate-100 flex flex-col gap-2.5">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-slate-600">
          {COLS_BG.map((bgClass, i) => (
            <span key={LAB[i]} className="inline-flex items-center gap-1.5 whitespace-nowrap">
              <span
                className={`w-3 h-3 rounded-xs border border-slate-900/20 shrink-0 ${bgClass}`}
              />
              <span>{LAB[i]}</span>
            </span>
          ))}
          <span className="inline-flex items-center gap-1.5 whitespace-nowrap">
            <span
              className={`w-3 h-3 rounded-xs border border-slate-900/20 shrink-0 ${NA_BG}`}
            />
            <span>n/a (hyper-arid)</span>
          </span>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
          <span>
            {sizeMode === 'var'
              ? 'Marker radius proportional to interannual rainfall variability (CV)'
              : 'Marker radius proportional to anomaly severity'}
          </span>
          <span>Thick marker stroke indicates Central Asian / regional agricultural focus</span>
        </div>
      </div>
    </div>
  );
};
