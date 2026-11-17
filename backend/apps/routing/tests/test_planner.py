"""End-to-end planner test using fake providers (no network)."""
from datetime import datetime, timedelta, timezone

from apps.providers.base import (
    GeocodeResult,
    GeoPoint,
    HourlyWeather,
    Route,
)
from apps.routing.services.planner import TripPlanner


class FakeGeocoder:
    def geocode(self, query):
        # Map two known queries to fixed points.
        coords = {
            "A": GeoPoint(39.0, -104.0),
            "B": GeoPoint(40.0, -111.0),
        }
        return GeocodeResult(point=coords.get(query, GeoPoint(39.5, -107.0)), display_name=query)


class FakeRouter:
    """Two routes: a calm direct one and a northern detour that hits a storm."""

    def routes(self, origin, destination, alternatives):
        calm = Route(
            # Stays at/below lat 40.0 the whole way.
            geometry=[(39.0, -104.0), (39.5, -107.0), (40.0, -111.0)],
            distance_meters=500 * 1609.344,
            duration_seconds=8 * 3600,
            label="Route A",
        )
        stormy = Route(
            # Detours north through lat ~41.0 — into the storm band (lat > 40.5).
            geometry=[(39.0, -104.0), (41.0, -107.0), (40.0, -111.0)],
            distance_meters=520 * 1609.344,
            duration_seconds=9 * 3600,
            label="Route B",
        )
        return [calm, stormy][:alternatives] if alternatives > 1 else [calm]


class FakeWeather:
    """Calm everywhere except the northern storm band (lat > 40.5), which only
    the detour route enters."""

    def forecast(self, points, start, end):
        hours = []
        t = start
        while t <= end:
            hours.append(t)
            t += timedelta(hours=1)
        out = []
        for p in points:
            stormy = p.lat > 40.5
            wind = [50.0 if stormy else 5.0] * len(hours)
            rain = [0.0] * len(hours)
            snow = [0.0] * len(hours)
            temp = [40.0] * len(hours)
            out.append(HourlyWeather(p, hours, wind, rain, snow, temp))
        return out


def make_planner():
    return TripPlanner(FakeGeocoder(), FakeRouter(), FakeWeather(), forecast_horizon_hours=48)


def test_plan_produces_routes_checkpoints_and_recommendation():
    planner = make_planner()
    plan = planner.plan(
        origin="A",
        destination="B",
        departure=datetime(2026, 11, 18, 8, tzinfo=timezone.utc),
        load_lb=20_000,
        interval_miles=50,
        alternatives=2,
    )
    assert len(plan.routes) == 2
    # Every route has checkpoints with ETAs after departure.
    for route in plan.routes:
        assert route.checkpoints
        assert route.checkpoints[0].eta == plan.departure
        assert route.checkpoints[-1].eta > plan.departure

    # The calm route (A) should be recommended over the stormy one (B).
    assert plan.recommended_index == 0
    assert plan.routes[0].is_recommended is True


def test_load_escalation_changes_recommendation_inputs():
    planner = make_planner()
    # Heavy load turns the stormy route's 50mph Severe wind into No-Travel.
    plan = planner.plan(
        origin="A", destination="B",
        departure=datetime(2026, 11, 18, 8, tzinfo=timezone.utc),
        load_lb=35_000, interval_miles=25, alternatives=2,
    )
    stormy = plan.routes[1]
    assert stormy.summary.has_no_travel is True
    assert plan.recommended_index == 0


def test_heatmap_covers_horizon():
    planner = make_planner()
    plan = planner.plan(
        origin="A", destination="B",
        departure=datetime(2026, 11, 18, 8, tzinfo=timezone.utc),
        load_lb=0, interval_miles=50, alternatives=2,
    )
    assert plan.heatmap is not None
    assert len(plan.heatmap.times) == 49  # 0..48 inclusive
    assert plan.heatmap.cells
    # Each cell has a risk value per hour.
    assert all(len(c.risk_by_hour) == 49 for c in plan.heatmap.cells)
