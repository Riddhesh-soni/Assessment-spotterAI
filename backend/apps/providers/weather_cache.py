"""
Process-local weather cache shared by all weather providers.

Keyed by (rounded coordinate, time window). Weather varies slowly over ~1 km, so
rounding to ~0.01 deg safely coalesces identical checkpoint/grid points across
repeated plans without materially changing the forecast — which keeps us well
under provider rate limits during repeated planning (e.g. a demo).
"""
from __future__ import annotations

import time

from .base import GeoPoint, HourlyWeather

_CACHE: dict[tuple, tuple[float, HourlyWeather]] = {}


def _key(point: GeoPoint, start_key: str, end_key: str) -> tuple:
    return (round(point.lat, 2), round(point.lng, 2), start_key, end_key)


def cache_get(point: GeoPoint, start_key: str, end_key: str, ttl: int) -> HourlyWeather | None:
    entry = _CACHE.get(_key(point, start_key, end_key))
    if entry is None:
        return None
    stored_at, value = entry
    if time.monotonic() - stored_at > ttl:
        return None
    return value


def cache_set(point: GeoPoint, start_key: str, end_key: str, value: HourlyWeather) -> None:
    _CACHE[_key(point, start_key, end_key)] = (time.monotonic(), value)
