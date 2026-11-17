"""Tests for polyline distance + checkpoint sampling."""
import math

from apps.routing.services import geometry


# A roughly west-to-east straight line near the equator keeps distances simple.
def test_haversine_known_distance():
    # 1 degree of longitude at the equator ~= 69.17 miles.
    d = geometry.haversine_miles((0.0, 0.0), (0.0, 1.0))
    assert abs(d - 69.17) < 0.5


def test_cumulative_miles_monotonic():
    line = [(0.0, 0.0), (0.0, 0.5), (0.0, 1.0)]
    cum = geometry.cumulative_miles(line)
    assert cum[0] == 0.0
    assert cum[1] < cum[2]
    assert abs(cum[2] - geometry.haversine_miles((0, 0), (0, 1))) < 1e-6


def test_point_at_distance_midpoint():
    line = [(0.0, 0.0), (0.0, 1.0)]
    cum = geometry.cumulative_miles(line)
    total = cum[-1]
    mid = geometry.point_at_distance(line, cum, total / 2)
    assert abs(mid[1] - 0.5) < 1e-6


def test_sample_checkpoints_partitions_route():
    line = [(0.0, 0.0), (0.0, 1.0)]  # ~69 miles
    total = geometry.cumulative_miles(line)[-1]
    cps = geometry.sample_checkpoints(line, interval_miles=25)
    # Segment miles must sum to the full route length.
    assert abs(sum(c.segment_miles for c in cps) - total) < 1e-6
    # First checkpoint at start, last at destination.
    assert cps[0].distance_from_start_miles == 0.0
    assert abs(cps[-1].distance_from_start_miles - total) < 1e-6
    # Interior checkpoints spaced by the interval.
    assert abs(cps[1].distance_from_start_miles - 25) < 1e-6


def test_simplify_caps_points_and_keeps_endpoints():
    line = [(0.0, i / 100) for i in range(1000)]
    reduced = geometry.simplify(line, max_points=50)
    assert len(reduced) <= 51
    assert reduced[0] == line[0]
    assert reduced[-1] == line[-1]


def test_grid_points_count():
    bbox = (0.0, 0.0, 1.0, 1.0)
    pts = geometry.grid_points(bbox, cols=5, rows=4)
    assert len(pts) == 20
    assert all(0.0 <= lat <= 1.0 and 0.0 <= lng <= 1.0 for lat, lng in pts)
