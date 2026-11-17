"""
Route geometry helpers: distance along a polyline and checkpoint sampling.

Pure functions (no Django/IO) so they're unit-testable in isolation. Distances
are in **miles** throughout to match the spec's sampling intervals.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

EARTH_RADIUS_MILES = 3958.7613


@dataclass(frozen=True)
class Checkpoint:
    lat: float
    lng: float
    distance_from_start_miles: float
    # Representative road length this checkpoint "owns" (for risk weighting).
    segment_miles: float


def haversine_miles(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle distance between two (lat, lng) points, in miles."""
    lat1, lng1 = math.radians(a[0]), math.radians(a[1])
    lat2, lng2 = math.radians(b[0]), math.radians(b[1])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(h))


def cumulative_miles(polyline: list[tuple[float, float]]) -> list[float]:
    """Cumulative distance to each vertex of the polyline (first element is 0)."""
    cum = [0.0]
    for i in range(1, len(polyline)):
        cum.append(cum[-1] + haversine_miles(polyline[i - 1], polyline[i]))
    return cum


def _interpolate(p0: tuple[float, float], p1: tuple[float, float], frac: float) -> tuple[float, float]:
    """Linear interpolation between two points (good enough at checkpoint scale)."""
    return (p0[0] + (p1[0] - p0[0]) * frac, p0[1] + (p1[1] - p0[1]) * frac)


def point_at_distance(
    polyline: list[tuple[float, float]], cum: list[float], target_miles: float
) -> tuple[float, float]:
    """Return the (lat, lng) at ``target_miles`` along the polyline."""
    if target_miles <= 0:
        return polyline[0]
    total = cum[-1]
    if target_miles >= total:
        return polyline[-1]
    # Find the segment [i-1, i] that contains the target distance.
    for i in range(1, len(cum)):
        if cum[i] >= target_miles:
            seg_len = cum[i] - cum[i - 1]
            frac = (target_miles - cum[i - 1]) / seg_len if seg_len else 0.0
            return _interpolate(polyline[i - 1], polyline[i], frac)
    return polyline[-1]


def sample_checkpoints(
    polyline: list[tuple[float, float]], interval_miles: float
) -> list[Checkpoint]:
    """Place a checkpoint every ``interval_miles`` along the route.

    Always includes the start (0 mi) and the destination (total mi). Each
    checkpoint's ``segment_miles`` is a trapezoidal attribution — the distance
    from the midpoint to the previous checkpoint to the midpoint to the next — so
    the segments partition the whole route exactly (they sum to total miles) and
    every checkpoint carries non-zero weight.
    """
    if len(polyline) < 2:
        raise ValueError("Polyline needs at least two points")
    if interval_miles <= 0:
        raise ValueError("interval_miles must be positive")

    cum = cumulative_miles(polyline)
    total = cum[-1]

    # Target distances: 0, interval, 2*interval, ... plus the exact endpoint.
    targets: list[float] = []
    d = 0.0
    while d < total:
        targets.append(d)
        d += interval_miles
    targets.append(total)

    # Trapezoidal segment boundaries: midpoints between consecutive targets.
    boundaries = [0.0]
    for i in range(1, len(targets)):
        boundaries.append((targets[i - 1] + targets[i]) / 2)
    boundaries.append(total)

    checkpoints: list[Checkpoint] = []
    for i, t in enumerate(targets):
        lat, lng = point_at_distance(polyline, cum, t)
        segment = boundaries[i + 1] - boundaries[i]
        checkpoints.append(
            Checkpoint(
                lat=lat,
                lng=lng,
                distance_from_start_miles=t,
                segment_miles=segment,
            )
        )
    return checkpoints


def bounding_box(
    polylines: list[list[tuple[float, float]]], margin_deg: float = 0.25
) -> tuple[float, float, float, float]:
    """Return (min_lat, min_lng, max_lat, max_lng) covering all polylines + margin."""
    lats = [pt[0] for pl in polylines for pt in pl]
    lngs = [pt[1] for pl in polylines for pt in pl]
    return (
        min(lats) - margin_deg,
        min(lngs) - margin_deg,
        max(lats) + margin_deg,
        max(lngs) + margin_deg,
    )


def grid_points(
    bbox: tuple[float, float, float, float], cols: int, rows: int
) -> list[tuple[float, float]]:
    """Evenly spaced (lat, lng) grid covering the bounding box, for the heatmap."""
    min_lat, min_lng, max_lat, max_lng = bbox
    lat_step = (max_lat - min_lat) / max(rows - 1, 1)
    lng_step = (max_lng - min_lng) / max(cols - 1, 1)
    return [
        (min_lat + r * lat_step, min_lng + c * lng_step)
        for r in range(rows)
        for c in range(cols)
    ]


def simplify(polyline: list[tuple[float, float]], max_points: int) -> list[tuple[float, float]]:
    """Down-sample a polyline to at most ``max_points`` vertices (keeps endpoints).

    Routing APIs can return thousands of vertices; capping keeps the map payload
    small and rendering smooth without visibly changing the drawn route.
    """
    n = len(polyline)
    if n <= max_points or max_points < 2:
        return polyline
    stride = math.ceil(n / max_points)
    reduced = polyline[::stride]
    if reduced[-1] != polyline[-1]:
        reduced.append(polyline[-1])
    return reduced
