import { useMemo } from "react";
import { Rectangle } from "react-leaflet";

import type { Heatmap } from "@/types/plan";
import { riskColor } from "@/lib/risk";

interface Props {
  heatmap: Heatmap;
  hourIndex: number;
}

// Derive the grid cell size from the spacing between adjacent grid points so
// each cell renders as a filled rectangle with no gaps.
function useCellSize(heatmap: Heatmap) {
  return useMemo(() => {
    const lats = [...new Set(heatmap.cells.map((c) => c.lat))].sort((a, b) => a - b);
    const lngs = [...new Set(heatmap.cells.map((c) => c.lng))].sort((a, b) => a - b);
    const latStep = lats.length > 1 ? lats[1] - lats[0] : 0.2;
    const lngStep = lngs.length > 1 ? lngs[1] - lngs[0] : 0.2;
    return { latStep, lngStep };
  }, [heatmap]);
}

export function HeatmapLayer({ heatmap, hourIndex }: Props) {
  const { latStep, lngStep } = useCellSize(heatmap);

  return (
    <>
      {heatmap.cells.map((cell, i) => {
        const level = cell.risk_by_hour[hourIndex] ?? 0;
        const bounds: [[number, number], [number, number]] = [
          [cell.lat - latStep / 2, cell.lng - lngStep / 2],
          [cell.lat + latStep / 2, cell.lng + lngStep / 2],
        ];
        return (
          <Rectangle
            key={i}
            bounds={bounds}
            pathOptions={{
              stroke: false,
              fillColor: riskColor(level),
              // Low risk fades out so the map stays readable; higher risk pops.
              fillOpacity: level === 0 ? 0.08 : 0.28 + level * 0.07,
            }}
            interactive={false}
          />
        );
      })}
    </>
  );
}
