import { CircleMarker, Popup } from "react-leaflet";

import type { Route } from "@/types/plan";
import { formatTime, riskColor, riskLabel } from "@/lib/risk";

// Risk-coloured dots at each checkpoint of the selected route, with a popup
// explaining the weather, ETA and what drove the risk level.
export function CheckpointMarkers({ route }: { route: Route }) {
  return (
    <>
      {route.checkpoints.map((cp, i) => (
        <CircleMarker
          key={`${cp.lat},${cp.lng},${i}`}
          center={[cp.lat, cp.lng]}
          radius={7}
          pathOptions={{
            color: "#ffffff",
            weight: 1.5,
            fillColor: riskColor(cp.risk.level),
            fillOpacity: 1,
          }}
        >
          <Popup>
            <div className="cp-popup">
              <strong>{riskLabel(cp.risk.level)}</strong>
              <span className="cp-sub">
                {cp.distance_miles.toFixed(0)} mi · ETA {formatTime(cp.eta)}
              </span>
              <ul>
                <li>Wind: {cp.weather.wind_mph.toFixed(0)} mph</li>
                <li>Rain: {cp.weather.rain_in_per_hr.toFixed(2)} in/hr</li>
                <li>Snow: {cp.weather.snow_in_per_hr.toFixed(2)} in/hr</li>
              </ul>
              {cp.risk.drivers.length > 0 && (
                <span className="cp-driver">Driven by: {cp.risk.drivers.join(", ")}</span>
              )}
            </div>
          </Popup>
        </CircleMarker>
      ))}
    </>
  );
}
