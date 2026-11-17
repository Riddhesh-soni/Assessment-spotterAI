// Type definitions mirroring the backend /api/plan/ response contract.
// Keeping these in one place means the whole UI shares one source of truth.

export type RiskLevelValue = 0 | 1 | 2 | 3 | 4;

export type LatLng = [number, number];

export interface PlanRequest {
  origin: string;
  destination: string;
  departure: string; // ISO 8601
  load_lb: number;
  interval_miles?: 10 | 25 | 50;
  alternatives?: number;
}

export interface Weather {
  wind_mph: number;
  rain_in_per_hr: number;
  snow_in_per_hr: number;
  temperature_f: number | null;
  forecast_time: string | null;
}

export interface CheckpointRisk {
  level: RiskLevelValue;
  label: string;
  drivers: string[];
  by_condition: Record<string, number>;
}

export interface Checkpoint {
  lat: number;
  lng: number;
  distance_miles: number;
  eta: string;
  weather: Weather;
  risk: CheckpointRisk;
}

export interface RouteSummary {
  total_miles: number;
  travel_time_seconds: number;
  average_risk: number;
  has_no_travel: boolean;
  miles_by_level: Record<string, number>;
}

export interface Route {
  label: string;
  is_recommended: boolean;
  geometry: LatLng[];
  distance_miles: number;
  duration_seconds: number;
  eta_arrival: string;
  summary: RouteSummary;
  checkpoints: Checkpoint[];
}

export interface HeatmapCell {
  lat: number;
  lng: number;
  risk_by_hour: RiskLevelValue[];
}

export interface Heatmap {
  times: string[];
  bbox: { min_lat: number; min_lng: number; max_lat: number; max_lng: number };
  cells: HeatmapCell[];
}

export interface GeoLabel {
  label: string;
  lat: number;
  lng: number;
}

export interface PlanResponse {
  query: {
    origin: GeoLabel;
    destination: GeoLabel;
    departure: string;
    load_lb: number;
    sampling_interval_miles: number;
  };
  recommended_index: number | null;
  routes: Route[];
  heatmap: Heatmap;
  risk_legend: { level: RiskLevelValue; label: string }[];
}
