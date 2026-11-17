"""
Open-Meteo weather provider — free, no API key, hourly forecasts.

Two design choices worth noting:

1. **Batching.** Open-Meteo accepts comma-separated coordinates and returns one
   result per location, so every checkpoint on a route is fetched in a *single*
   HTTP call. With 3 routes that's ~3 upstream calls total instead of hundreds.

2. **Defensive unit normalisation.** Rather than trust the requested units, we
   read ``hourly_units`` from the response and convert wind -> mph, rain -> in/hr,
   snow -> in/hr ourselves. This makes the risk engine's thresholds reliable
   regardless of any upstream unit default changes.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .base import (
    GeoPoint,
    HourlyWeather,
    UpstreamError,
    WeatherProvider,  # noqa: F401  (documents the interface this satisfies)
    request_json,
)

# Conversion factors to the spec's units.
# Open-Meteo reports mph as "mp/h"; include common aliases for robustness.
_WIND_TO_MPH = {"mph": 1.0, "mp/h": 1.0, "km/h": 0.621371, "kmh": 0.621371, "m/s": 2.236936, "kn": 1.150779, "knots": 1.150779}
_LEN_TO_INCH = {"inch": 1.0, "in": 1.0, "mm": 1.0 / 25.4, "cm": 1.0 / 2.54, "m": 39.3701}


def _convert(values: list, factor_table: dict, unit: str, field: str) -> list[float]:
    key = (unit or "").strip().lower()
    if key not in factor_table:
        raise UpstreamError(f"Unknown {field} unit from weather API: {unit!r}")
    factor = factor_table[key]
    return [float(v) * factor if v is not None else 0.0 for v in values]


class OpenMeteoProvider:
    def __init__(self, base_url: str, timeout: int):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def forecast(
        self, points: list[GeoPoint], start: datetime, end: datetime
    ) -> list[HourlyWeather]:
        if not points:
            return []

        params = {
            "latitude": ",".join(f"{p.lat:.5f}" for p in points),
            "longitude": ",".join(f"{p.lng:.5f}" for p in points),
            "hourly": "wind_speed_10m,rain,snowfall,temperature_2m",
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
            "temperature_unit": "fahrenheit",
            "timezone": "UTC",
            "start_hour": start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:00"),
            "end_hour": end.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:00"),
        }
        data = request_json(
            "GET", f"{self._base_url}/forecast", timeout=self._timeout, params=params
        )

        # Single location -> dict; multiple -> list. Normalise to a list.
        locations = data if isinstance(data, list) else [data]
        if len(locations) != len(points):
            raise UpstreamError(
                f"Weather API returned {len(locations)} locations for {len(points)} points"
            )

        return [self._parse_location(loc, point) for loc, point in zip(locations, points)]

    @staticmethod
    def _parse_location(loc: dict, point: GeoPoint) -> HourlyWeather:
        hourly = loc.get("hourly")
        units = loc.get("hourly_units", {})
        if not hourly or "time" not in hourly:
            raise UpstreamError("Weather API response missing hourly data")

        times = [
            datetime.fromisoformat(t).replace(tzinfo=timezone.utc)
            for t in hourly["time"]
        ]
        return HourlyWeather(
            point=point,
            times=times,
            wind_mph=_convert(hourly.get("wind_speed_10m", []), _WIND_TO_MPH, units.get("wind_speed_10m", "mph"), "wind"),
            rain_in_per_hr=_convert(hourly.get("rain", []), _LEN_TO_INCH, units.get("rain", "inch"), "rain"),
            snow_in_per_hr=_convert(hourly.get("snowfall", []), _LEN_TO_INCH, units.get("snowfall", "cm"), "snow"),
            temperature_f=[float(v) if v is not None else 0.0 for v in hourly.get("temperature_2m", [])],
        )
