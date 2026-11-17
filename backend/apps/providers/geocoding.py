"""
Geocoding providers.

Two implementations:
  * ``NominatimGeocoder`` — free, no key; great for local dev but Nominatim's
    public server rate-limits/blocks shared cloud IPs (429), so it's unreliable
    when hosted.
  * ``OpenRouteServiceGeocoder`` — Pelias-based, uses the same ORS key we already
    have for routing; production-grade and the default (see the provider factory).
"""
from __future__ import annotations

from .base import (
    GeocodingError,
    GeocodeResult,
    GeoPoint,
    ProviderConfigError,
    request_json,
)


class NominatimGeocoder:
    """Resolve a free-text address/place to coordinates via Nominatim.

    Note: Nominatim's usage policy requires a descriptive User-Agent and limits
    to ~1 request/second. Geocoding happens twice per plan (origin + dest), so
    we stay well within limits.
    """

    def __init__(self, base_url: str, user_agent: str, timeout: int):
        self._base_url = base_url.rstrip("/")
        self._user_agent = user_agent
        self._timeout = timeout

    def geocode(self, query: str) -> GeocodeResult:
        query = (query or "").strip()
        if not query:
            raise GeocodingError("Empty location query")

        data = request_json(
            "GET",
            f"{self._base_url}/search",
            timeout=self._timeout,
            headers={"User-Agent": self._user_agent},
            params={"q": query, "format": "jsonv2", "limit": 1},
        )
        if not isinstance(data, list) or not data:
            raise GeocodingError(f"Could not geocode location: {query!r}")

        top = data[0]
        try:
            point = GeoPoint(lat=float(top["lat"]), lng=float(top["lon"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise GeocodingError(f"Malformed geocoding result for {query!r}") from exc

        return GeocodeResult(point=point, display_name=top.get("display_name", query))


class OpenRouteServiceGeocoder:
    """Resolve a free-text address/place to coordinates via ORS (Pelias).

    Reuses the OpenRouteService API key already configured for routing. ORS's
    geocoding endpoint authenticates with the key as a query parameter and
    returns GeoJSON with [lng, lat] coordinates.
    """

    def __init__(self, api_key: str, base_url: str, timeout: int):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def geocode(self, query: str) -> GeocodeResult:
        query = (query or "").strip()
        if not query:
            raise GeocodingError("Empty location query")
        if not self._api_key:
            raise ProviderConfigError(
                "ORS_API_KEY is not set. Get a free key at openrouteservice.org."
            )

        data = request_json(
            "GET",
            f"{self._base_url}/geocode/search",
            timeout=self._timeout,
            params={"api_key": self._api_key, "text": query, "size": 1},
        )
        features = data.get("features") if isinstance(data, dict) else None
        if not features:
            raise GeocodingError(f"Could not geocode location: {query!r}")

        top = features[0]
        try:
            lng, lat = top["geometry"]["coordinates"][:2]
            point = GeoPoint(lat=float(lat), lng=float(lng))
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            raise GeocodingError(f"Malformed geocoding result for {query!r}") from exc

        label = top.get("properties", {}).get("label", query)
        return GeocodeResult(point=point, display_name=label)
