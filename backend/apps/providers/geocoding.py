"""Nominatim (OpenStreetMap) geocoding provider — free, no API key."""
from __future__ import annotations

from .base import (
    GeocodingError,
    GeocodeResult,
    GeoPoint,
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
