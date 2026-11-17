import { useMemo } from "react";
import { Marker } from "react-leaflet";
import L from "leaflet";

import type { GeoLabel } from "@/types/plan";

// divIcon markers are rendered as DOM (not canvas), so they can carry a CSS
// pulse animation while the heavy vector layers stay on canvas for performance.
function pulsePin(color: string, label: string): L.DivIcon {
  return L.divIcon({
    className: "endpoint-pin-wrap",
    html: `
      <div class="endpoint-pin" title="${label}">
        <span class="endpoint-pin__pulse" style="background:${color}"></span>
        <span class="endpoint-pin__dot" style="background:${color}"></span>
      </div>`,
    iconSize: [18, 18],
    iconAnchor: [9, 9],
  });
}

interface Props {
  origin: GeoLabel;
  destination: GeoLabel;
}

export function EndpointMarkers({ origin, destination }: Props) {
  const originIcon = useMemo(() => pulsePin("#22c55e", origin.label), [origin.label]);
  const destIcon = useMemo(() => pulsePin("#38bdf8", destination.label), [destination.label]);

  return (
    <>
      <Marker position={[origin.lat, origin.lng]} icon={originIcon} />
      <Marker position={[destination.lat, destination.lng]} icon={destIcon} />
    </>
  );
}
