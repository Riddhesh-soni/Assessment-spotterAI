import { useEffect } from "react";
import { useMap } from "react-leaflet";
import L from "leaflet";

import type { LatLng } from "@/types/plan";

// Imperatively fit the map viewport to all route geometry whenever it changes.
export function FitBounds({ geometries }: { geometries: LatLng[][] }) {
  const map = useMap();

  useEffect(() => {
    const points = geometries.flat();
    if (points.length === 0) return;
    const bounds = L.latLngBounds(points.map(([lat, lng]) => [lat, lng]));
    // Smooth animated framing rather than an instant jump.
    map.flyToBounds(bounds, { padding: [48, 48], duration: 0.9, easeLinearity: 0.25 });
  }, [map, geometries]);

  return null;
}
