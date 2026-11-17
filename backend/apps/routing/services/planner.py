"""
Trip planner — the orchestration layer.

Given a trip request it:
  1. geocodes origin + destination,
  2. asks the routing provider for N alternative routes,
  3. samples checkpoints along each route and computes each checkpoint's ETA,
  4. fetches weather for every checkpoint (batched) at its arrival hour,
  5. classifies risk per checkpoint and summarises/ranks the routes, and
  6. builds a corridor weather grid for the 0–48h heatmap.

It depends only on the provider *interfaces* and the pure risk engine, so it can
be tested end-to-end with fake providers (see tests/test_planner.py).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from apps.providers.base import (
    GeocodingProvider,
    GeoPoint,
    HourlyWeather,
    RoutingProvider,
    UpstreamError,
    WeatherProvider,
)
from apps.risk.engine import classify_checkpoint, rank_routes, summarize_route
from apps.risk.models import CheckpointRisk, RouteRiskSummary, WeatherSample

from . import geometry

METERS_PER_MILE = 1609.344
# Open-Meteo accepts many locations per call; chunk to stay comfortably within limits.
WEATHER_BATCH_SIZE = 100
# Cap route polyline vertices sent to the client (map performance).
MAX_GEOMETRY_POINTS = 400
# Heatmap grid density. Kept modest so the corridor forecast stays within the
# weather provider's rate limits while still reading clearly on the map.
HEATMAP_COLS = 10
HEATMAP_ROWS = 6


# --------------------------------------------------------------------------- #
# Result data structures (what the API serialises)
# --------------------------------------------------------------------------- #
@dataclass
class CheckpointResult:
    lat: float
    lng: float
    distance_miles: float
    eta: datetime
    weather: WeatherSample
    risk: CheckpointRisk


@dataclass
class RouteResult:
    label: str
    geometry: list[tuple[float, float]]
    distance_miles: float
    duration_seconds: float
    eta_arrival: datetime
    checkpoints: list[CheckpointResult]
    summary: RouteRiskSummary
    is_recommended: bool = False


@dataclass
class HeatmapCell:
    lat: float
    lng: float
    risk_by_hour: list[int]  # risk level (0-4) for each hour in the horizon


@dataclass
class Heatmap:
    times: list[datetime]
    bbox: tuple[float, float, float, float]
    cells: list[HeatmapCell]


@dataclass
class PlanResult:
    origin: GeoPoint
    destination: GeoPoint
    origin_label: str
    destination_label: str
    departure: datetime
    load_lb: float
    sampling_interval_miles: float
    routes: list[RouteResult]
    recommended_index: int | None
    heatmap: Heatmap = field(default=None)  # type: ignore[assignment]


class TripPlanner:
    def __init__(
        self,
        geocoder: GeocodingProvider,
        router: RoutingProvider,
        weather: WeatherProvider,
        forecast_horizon_hours: int = 48,
    ):
        self._geocoder = geocoder
        self._router = router
        self._weather = weather
        self._horizon = forecast_horizon_hours

    # ------------------------------------------------------------------ #
    # Public entry point
    # ------------------------------------------------------------------ #
    def plan(
        self,
        origin: str,
        destination: str,
        departure: datetime,
        load_lb: float,
        interval_miles: float,
        alternatives: int = 3,
    ) -> PlanResult:
        departure = _ensure_utc(departure)

        origin_geo = self._geocoder.geocode(origin)
        dest_geo = self._geocoder.geocode(destination)

        raw_routes = self._router.routes(origin_geo.point, dest_geo.point, alternatives)

        # Sample checkpoints + ETAs for every route up front so we can batch the
        # weather lookup across all of them in one pass.
        sampled: list[list[geometry.Checkpoint]] = []
        etas: list[list[datetime]] = []
        for route in raw_routes:
            checkpoints = geometry.sample_checkpoints(route.geometry, interval_miles)
            sampled.append(checkpoints)
            etas.append(_checkpoint_etas(route, checkpoints, departure))

        # Weather window: from departure to the later of the forecast horizon and
        # the slowest route's arrival, so every checkpoint ETA is covered.
        latest_eta = max((e[-1] for e in etas if e), default=departure)
        window_end = max(departure + timedelta(hours=self._horizon), latest_eta)

        # Batch weather for all checkpoints across all routes.
        all_points = [GeoPoint(c.lat, c.lng) for route_cps in sampled for c in route_cps]
        weather_by_point = self._fetch_weather(all_points, departure, window_end)

        routes: list[RouteResult] = []
        cursor = 0
        for route, checkpoints, route_etas in zip(raw_routes, sampled, etas):
            cp_results: list[CheckpointResult] = []
            levels = []
            seg_miles = []
            for cp, eta in zip(checkpoints, route_etas):
                hw = weather_by_point[cursor]
                cursor += 1
                sample = _to_weather_sample(hw, eta)
                risk = classify_checkpoint(sample, load_lb)
                cp_results.append(
                    CheckpointResult(
                        lat=cp.lat, lng=cp.lng,
                        distance_miles=cp.distance_from_start_miles,
                        eta=eta, weather=sample, risk=risk,
                    )
                )
                levels.append(risk.level)
                seg_miles.append(cp.segment_miles)

            summary = summarize_route(levels, seg_miles, route.duration_seconds)
            routes.append(
                RouteResult(
                    label=route.label,
                    geometry=geometry.simplify(route.geometry, MAX_GEOMETRY_POINTS),
                    distance_miles=route.distance_meters / METERS_PER_MILE,
                    duration_seconds=route.duration_seconds,
                    eta_arrival=departure + timedelta(seconds=route.duration_seconds),
                    checkpoints=cp_results,
                    summary=summary,
                )
            )

        ranking = rank_routes([r.summary for r in routes])
        recommended = ranking[0] if ranking else None
        if recommended is not None:
            routes[recommended].is_recommended = True

        # The corridor heatmap is the heaviest weather consumer. If it gets
        # rate-limited, don't fail the whole plan — return the routes + checkpoint
        # risk (the core feature) with an empty heatmap the UI can handle.
        polylines = [r.geometry for r in routes]
        try:
            heatmap = self._build_heatmap(polylines, departure, load_lb)
        except UpstreamError:
            hours = [departure + timedelta(hours=h) for h in range(self._horizon + 1)]
            heatmap = Heatmap(
                times=hours, bbox=geometry.bounding_box(polylines), cells=[]
            )

        return PlanResult(
            origin=origin_geo.point,
            destination=dest_geo.point,
            origin_label=origin_geo.display_name,
            destination_label=dest_geo.display_name,
            departure=departure,
            load_lb=load_lb,
            sampling_interval_miles=interval_miles,
            routes=routes,
            recommended_index=recommended,
            heatmap=heatmap,
        )

    # ------------------------------------------------------------------ #
    # Weather helpers
    # ------------------------------------------------------------------ #
    def _fetch_weather(
        self, points: list[GeoPoint], start: datetime, end: datetime
    ) -> list[HourlyWeather]:
        """Fetch weather for all points, chunked to respect API limits."""
        results: list[HourlyWeather] = []
        for i in range(0, len(points), WEATHER_BATCH_SIZE):
            chunk = points[i : i + WEATHER_BATCH_SIZE]
            results.extend(self._weather.forecast(chunk, start, end))
        return results

    def _build_heatmap(
        self,
        polylines: list[list[tuple[float, float]]],
        departure: datetime,
        load_lb: float,
    ) -> Heatmap:
        """Classify a corridor grid at each hour of the forecast horizon."""
        bbox = geometry.bounding_box(polylines)
        grid = geometry.grid_points(bbox, HEATMAP_COLS, HEATMAP_ROWS)
        points = [GeoPoint(lat, lng) for lat, lng in grid]
        hours = [departure + timedelta(hours=h) for h in range(self._horizon + 1)]

        weather = self._fetch_weather(points, departure, hours[-1])

        cells: list[HeatmapCell] = []
        for pt, hw in zip(points, weather):
            risk_by_hour = []
            for when in hours:
                sample = _to_weather_sample(hw, when)
                risk_by_hour.append(int(classify_checkpoint(sample, load_lb).level))
            cells.append(HeatmapCell(lat=pt.lat, lng=pt.lng, risk_by_hour=risk_by_hour))

        return Heatmap(times=hours, bbox=bbox, cells=cells)


# --------------------------------------------------------------------------- #
# Module-level helpers
# --------------------------------------------------------------------------- #
def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _checkpoint_etas(route, checkpoints, departure: datetime) -> list[datetime]:
    """Estimate arrival time at each checkpoint.

    Assumes uniform speed over the route (total duration / total distance from the
    routing provider), so ETA at distance d = departure + duration * (d / total).
    This uses the provider's own time estimate, scaled by distance travelled.
    """
    total_miles = route.distance_meters / METERS_PER_MILE
    etas = []
    for cp in checkpoints:
        frac = (cp.distance_from_start_miles / total_miles) if total_miles else 0.0
        etas.append(departure + timedelta(seconds=route.duration_seconds * frac))
    return etas


def _to_weather_sample(hw: HourlyWeather, when: datetime) -> WeatherSample:
    values = hw.at(when)
    return WeatherSample(
        wind_mph=values["wind_mph"],
        rain_in_per_hr=values["rain_in_per_hr"],
        snow_in_per_hr=values["snow_in_per_hr"],
        temperature_f=values["temperature_f"],
        forecast_time_iso=values["time"].isoformat(),
    )
