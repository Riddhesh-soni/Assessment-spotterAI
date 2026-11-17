"""
WeatherAPI.com weather provider.

Chosen for hosting because its free tier quota is tied to the **API key**, not the
client IP — unlike Open-Meteo/Nominatim, whose per-IP limits are shared (and
exhausted) across all tenants on a cloud provider's outbound IPs.

WeatherAPI has no multi-location endpoint, so points are fetched concurrently
with a small thread pool, and the shared weather cache keeps repeated plans free.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from .base import (
    GeoPoint,
    HourlyWeather,
    ProviderConfigError,
    UpstreamError,
    WeatherProvider,  # noqa: F401  (documents the interface this satisfies)
    request_json,
)
from .weather_cache import cache_get, cache_set

_CM_TO_INCH = 1.0 / 2.54
# WeatherAPI free plan allows up to 3 forecast days (72h) — enough for a next-day
# departure plus the 48h horizon and typical trip durations.
_FORECAST_DAYS = 3


class WeatherAPIProvider:
    def __init__(self, api_key: str, base_url: str, timeout: int,
                 cache_ttl: int = 1800, max_workers: int = 8):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._cache_ttl = cache_ttl
        self._max_workers = max_workers

    def forecast(
        self, points: list[GeoPoint], start: datetime, end: datetime
    ) -> list[HourlyWeather]:
        if not points:
            return []
        if not self._api_key:
            raise ProviderConfigError(
                "WEATHERAPI_KEY is not set. Get a free key at weatherapi.com."
            )

        start_key = start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:00")
        end_key = end.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:00")

        # Serve cached points; fetch only the misses (concurrently).
        results: list[HourlyWeather | None] = [None] * len(points)
        miss_idx: list[int] = []
        miss_points: list[GeoPoint] = []
        for i, p in enumerate(points):
            cached = cache_get(p, start_key, end_key, self._cache_ttl)
            if cached is not None:
                results[i] = cached
            else:
                miss_idx.append(i)
                miss_points.append(p)

        if miss_points:
            workers = min(self._max_workers, len(miss_points))
            with ThreadPoolExecutor(max_workers=workers) as pool:
                fetched = list(pool.map(self._fetch_one, miss_points))
            for idx, point, hw in zip(miss_idx, miss_points, fetched):
                results[idx] = hw
                cache_set(point, start_key, end_key, hw)

        return [hw for hw in results if hw is not None]

    def _fetch_one(self, point: GeoPoint) -> HourlyWeather:
        data = request_json(
            "GET",
            f"{self._base_url}/forecast.json",
            timeout=self._timeout,
            params={
                "key": self._api_key,
                "q": f"{point.lat:.5f},{point.lng:.5f}",
                "days": _FORECAST_DAYS,
                "aqi": "no",
                "alerts": "no",
            },
        )
        return self._parse(point, data)

    @staticmethod
    def _parse(point: GeoPoint, data: dict) -> HourlyWeather:
        try:
            days = data["forecast"]["forecastday"]
        except (KeyError, TypeError) as exc:
            raise UpstreamError("WeatherAPI response missing forecast data") from exc

        times: list[datetime] = []
        wind: list[float] = []
        rain: list[float] = []
        snow: list[float] = []
        temp: list[float] = []
        for day in days:
            for hour in day.get("hour", []):
                snow_cm = float(hour.get("snow_cm", 0.0) or 0.0)
                snow_in = snow_cm * _CM_TO_INCH
                precip_in = float(hour.get("precip_in", 0.0) or 0.0)
                # When it's snowing, precip_in is the liquid-equivalent of the snow,
                # so don't also count it as rain.
                rain_in = 0.0 if snow_cm > 0 else precip_in

                times.append(datetime.fromtimestamp(hour["time_epoch"], tz=timezone.utc))
                wind.append(float(hour.get("wind_mph", 0.0) or 0.0))
                rain.append(rain_in)
                snow.append(snow_in)
                temp.append(float(hour.get("temp_f", 0.0) or 0.0))

        if not times:
            raise UpstreamError("WeatherAPI response contained no hourly data")

        return HourlyWeather(
            point=point, times=times, wind_mph=wind,
            rain_in_per_hr=rain, snow_in_per_hr=snow, temperature_f=temp,
        )
