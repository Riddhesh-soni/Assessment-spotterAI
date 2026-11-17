"""
OpenRouteService routing provider.

Uses the ``driving-hgv`` (heavy goods vehicle) profile — appropriate for a truck.

Getting multiple route options is handled in two ways because ORS's public API
caps its native ``alternative_routes`` algorithm at ~100 km:

  * **Short trips (<= 100 km):** request ORS's native alternative routes — the
    best-quality, genuinely distinct options.
  * **Long trips (> 100 km):** the native algorithm is unavailable, so we
    synthesize alternatives by routing the primary path, then re-routing through
    waypoints offset laterally from the route's midpoint. ORS snaps each waypoint
    to the nearest road, yielding distinct real-road detours at any distance.

Both paths reuse the same ORS key and ``driving-hgv`` profile.
"""
from __future__ import annotations

import math

from .base import (
    GeoPoint,
    ProviderConfigError,
    Route,
    UpstreamError,
    request_json,
)

_ROUTE_LABELS = ("Route A", "Route B", "Route C", "Route D", "Route E")

# ORS public-server limit for the alternative-routes algorithm.
_ALT_ALGO_MAX_METERS = 100_000
# Lateral offset for synthesized waypoints, as a fraction of the trip's
# coordinate span. Larger = bigger detours. A spread of magnitudes improves the
# odds of finding genuinely distinct corridors where the road network has them.
_OFFSET_FRACTIONS = (0.12, 0.18, 0.26, 0.35)


class OpenRouteServiceProvider:
    def __init__(self, api_key: str, base_url: str, timeout: int, profile: str = "driving-hgv"):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._profile = profile

    def routes(self, origin: GeoPoint, destination: GeoPoint, alternatives: int) -> list[Route]:
        if not self._api_key:
            raise ProviderConfigError(
                "ORS_API_KEY is not set. Get a free key at openrouteservice.org."
            )

        # Always fetch the primary (optimal) route first — one call, also tells us
        # the trip distance so we can pick the alternatives strategy.
        primary = self._directions([origin, destination])[0]
        if alternatives <= 1:
            return self._labelled([primary])

        # Short enough for ORS's native alternative-routes algorithm.
        if primary.distance_meters <= _ALT_ALGO_MAX_METERS:
            try:
                native = self._directions(
                    [origin, destination], target_alternatives=alternatives
                )
                if len(native) >= 2:
                    return self._labelled(native[:alternatives])
            except UpstreamError:
                pass  # fall through to the synthesized strategy

        # Long trip (or native alternatives unavailable): synthesize detours.
        collected = [primary]
        for via in self._offset_waypoints(primary.geometry, origin, destination,
                                          needed=alternatives - 1):
            if len(collected) >= alternatives:
                break
            try:
                alt = self._directions([origin, via, destination])[0]
            except UpstreamError:
                continue  # waypoint unreachable (e.g. off-road) — skip it
            if self._is_distinct(alt, collected):
                collected.append(alt)

        return self._labelled(collected[:alternatives])

    # ------------------------------------------------------------------ #
    # ORS calls
    # ------------------------------------------------------------------ #
    def _directions(
        self, points: list[GeoPoint], target_alternatives: int | None = None
    ) -> list[Route]:
        body: dict = {
            "coordinates": [p.as_lng_lat() for p in points],
            "instructions": False,
        }
        if target_alternatives and target_alternatives > 1:
            body["alternative_routes"] = {
                "target_count": target_alternatives,
                "weight_factor": 1.6,  # allow routes up to 1.6x the optimal weight
                "share_factor": 0.6,   # max 60% shared geometry between options
            }

        data = request_json(
            "POST",
            f"{self._base_url}/v2/directions/{self._profile}/geojson",
            timeout=self._timeout,
            headers={"Authorization": self._api_key, "Content-Type": "application/json"},
            json_body=body,
        )
        return self._parse(data)

    @staticmethod
    def _parse(data) -> list[Route]:
        if not isinstance(data, dict) or "features" not in data:
            raise UpstreamError("Unexpected ORS response (no 'features')")

        routes: list[Route] = []
        for feature in data["features"]:
            geom = feature.get("geometry", {}).get("coordinates", [])
            summary = feature.get("properties", {}).get("summary", {})
            # GeoJSON is [lng, lat]; our domain uses [lat, lng].
            polyline = [(coord[1], coord[0]) for coord in geom]
            routes.append(
                Route(
                    geometry=polyline,
                    distance_meters=float(summary.get("distance", 0.0)),
                    duration_seconds=float(summary.get("duration", 0.0)),
                )
            )
        if not routes:
            raise UpstreamError("ORS returned no routes")
        return routes

    # ------------------------------------------------------------------ #
    # Synthesized-alternative helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _offset_waypoints(
        geometry: list[tuple[float, float]],
        origin: GeoPoint,
        destination: GeoPoint,
        needed: int,
    ) -> list[GeoPoint]:
        """Candidate via-points offset perpendicular to the trip, alternating
        sides and growing in magnitude so we can force distinct detours."""
        if not geometry:
            return []
        mid = geometry[len(geometry) // 2]

        # Unit vector perpendicular to the overall origin->destination direction.
        dlat = destination.lat - origin.lat
        dlng = destination.lng - origin.lng
        span = math.hypot(dlat, dlng) or 1e-6
        perp_lat, perp_lng = -dlng / span, dlat / span

        candidates: list[GeoPoint] = []
        # Produce more candidates than strictly needed so failures can be skipped.
        for frac in _OFFSET_FRACTIONS:
            mag = frac * span
            for sign in (1, -1):
                candidates.append(
                    GeoPoint(mid[0] + sign * perp_lat * mag, mid[1] + sign * perp_lng * mag)
                )
                if len(candidates) >= needed * 4:
                    return candidates
        return candidates

    @staticmethod
    def _is_distinct(candidate: Route, existing: list[Route]) -> bool:
        """Reject near-duplicate routes (within 3% distance of an existing one)."""
        for other in existing:
            if other.distance_meters == 0:
                continue
            if abs(candidate.distance_meters - other.distance_meters) / other.distance_meters < 0.03:
                return False
        return True

    @staticmethod
    def _labelled(routes: list[Route]) -> list[Route]:
        return [
            Route(
                geometry=r.geometry,
                distance_meters=r.distance_meters,
                duration_seconds=r.duration_seconds,
                label=_ROUTE_LABELS[i] if i < len(_ROUTE_LABELS) else f"Route {i + 1}",
            )
            for i, r in enumerate(routes)
        ]
