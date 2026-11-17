"""
Provider foundation: shared HTTP handling, typed data contracts, and the
interfaces (Protocols) that every concrete provider implements.

Why interfaces? The planner depends only on these Protocols, never on a concrete
vendor. Swapping OpenRouteService for Google, or Open-Meteo for Tomorrow.io, is a
one-line change in the factory (see ``apps/providers/__init__.py``) with zero
changes to business logic.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

import requests


# --------------------------------------------------------------------------- #
# Exceptions
# --------------------------------------------------------------------------- #
class ProviderError(Exception):
    """Base class for all provider failures."""


class ProviderConfigError(ProviderError):
    """Raised when a provider is missing required configuration (e.g. API key)."""


class UpstreamError(ProviderError):
    """Raised when an upstream API returns an error or unexpected payload."""


class GeocodingError(ProviderError):
    """Raised when an address cannot be resolved to coordinates."""


# --------------------------------------------------------------------------- #
# Data contracts (vendor-neutral)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class GeoPoint:
    lat: float
    lng: float

    def as_lng_lat(self) -> list[float]:
        """Many routing APIs (GeoJSON, ORS) expect [lng, lat] order."""
        return [self.lng, self.lat]


@dataclass(frozen=True)
class GeocodeResult:
    point: GeoPoint
    display_name: str


@dataclass(frozen=True)
class Route:
    """A single route option returned by a routing provider."""

    # Ordered [lat, lng] coordinates describing the route polyline.
    geometry: list[tuple[float, float]]
    distance_meters: float
    duration_seconds: float
    label: str = ""


@dataclass(frozen=True)
class HourlyWeather:
    """Weather for one point across an ordered series of hourly timestamps."""

    point: GeoPoint
    times: list[datetime]          # tz-aware UTC timestamps
    wind_mph: list[float]
    rain_in_per_hr: list[float]
    snow_in_per_hr: list[float]
    temperature_f: list[float]

    def at(self, when: datetime) -> dict:
        """Return the weather values for the hour bucket covering ``when``.

        Picks the latest sample whose timestamp is <= ``when`` (i.e. the hour the
        truck arrives within). Falls back to the first/last sample at the edges.
        """
        if not self.times:
            raise UpstreamError("No weather samples available for point")
        idx = 0
        for i, t in enumerate(self.times):
            if t <= when:
                idx = i
            else:
                break
        return {
            "time": self.times[idx],
            "wind_mph": self.wind_mph[idx],
            "rain_in_per_hr": self.rain_in_per_hr[idx],
            "snow_in_per_hr": self.snow_in_per_hr[idx],
            "temperature_f": self.temperature_f[idx],
        }


# --------------------------------------------------------------------------- #
# Interfaces
# --------------------------------------------------------------------------- #
@runtime_checkable
class GeocodingProvider(Protocol):
    def geocode(self, query: str) -> GeocodeResult: ...


@runtime_checkable
class RoutingProvider(Protocol):
    def routes(self, origin: GeoPoint, destination: GeoPoint, alternatives: int) -> list[Route]: ...


@runtime_checkable
class WeatherProvider(Protocol):
    def forecast(
        self, points: list[GeoPoint], start: datetime, end: datetime
    ) -> list[HourlyWeather]: ...


# --------------------------------------------------------------------------- #
# Shared HTTP helper
# --------------------------------------------------------------------------- #
def request_json(
    method: str,
    url: str,
    *,
    timeout: int,
    headers: dict | None = None,
    params: dict | None = None,
    json_body: dict | None = None,
) -> dict | list:
    """Perform an HTTP request and return parsed JSON, normalising errors.

    Any transport/HTTP/parse failure is re-raised as :class:`UpstreamError` so
    callers never have to catch vendor-specific ``requests`` exceptions.
    """
    try:
        resp = requests.request(
            method,
            url,
            headers=headers,
            params=params,
            json=json_body,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise UpstreamError(f"Request to {url} failed: {exc}") from exc

    if resp.status_code >= 400:
        raise UpstreamError(
            f"{url} returned {resp.status_code}: {resp.text[:300]}"
        )
    try:
        return resp.json()
    except ValueError as exc:
        raise UpstreamError(f"{url} returned non-JSON response") from exc
