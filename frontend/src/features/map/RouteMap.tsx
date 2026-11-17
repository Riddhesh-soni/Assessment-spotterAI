import { MapContainer, TileLayer } from "react-leaflet";
import "leaflet/dist/leaflet.css";

import type { PlanResponse } from "@/types/plan";
import { CheckpointMarkers } from "./CheckpointMarkers";
import { EndpointMarkers } from "./EndpointMarkers";
import { FitBounds } from "./FitBounds";
import { HeatmapLayer } from "./HeatmapLayer";
import { RouteLayer } from "./RouteLayer";

interface Props {
  plan: PlanResponse;
  selectedRoute: number;
  onSelectRoute: (index: number) => void;
  showHeatmap: boolean;
  hourIndex: number;
}

export function RouteMap({ plan, selectedRoute, onSelectRoute, showHeatmap, hourIndex }: Props) {
  const geometries = plan.routes.map((r) => r.geometry);

  return (
    <MapContainer
      center={[39.5, -107]}
      zoom={6}
      className="map"
      preferCanvas // canvas rendering keeps many markers/rectangles smooth
      scrollWheelZoom
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      {showHeatmap && <HeatmapLayer heatmap={plan.heatmap} hourIndex={hourIndex} />}

      <RouteLayer routes={plan.routes} selectedIndex={selectedRoute} onSelect={onSelectRoute} />
      {plan.routes[selectedRoute] && (
        <CheckpointMarkers route={plan.routes[selectedRoute]} />
      )}

      <EndpointMarkers origin={plan.query.origin} destination={plan.query.destination} />

      <FitBounds geometries={geometries} />
    </MapContainer>
  );
}
