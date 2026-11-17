import { Polyline } from "react-leaflet";

import type { Route } from "@/types/plan";

interface Props {
  routes: Route[];
  selectedIndex: number;
  onSelect: (index: number) => void;
}

// Draws each route polyline. The selected route is bold & opaque; others are
// thin & faded so the active choice stands out.
export function RouteLayer({ routes, selectedIndex, onSelect }: Props) {
  return (
    <>
      {routes.map((route, i) => {
        const selected = i === selectedIndex;
        return (
          <Polyline
            key={route.label}
            positions={route.geometry}
            pathOptions={{
              color: selected ? "#2563eb" : "#64748b",
              weight: selected ? 6 : 3,
              opacity: selected ? 0.95 : 0.5,
            }}
            eventHandlers={{ click: () => onSelect(i) }}
          />
        );
      })}
    </>
  );
}
