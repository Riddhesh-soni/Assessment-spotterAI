"""Checkpoint classification + route scoring/ranking tests."""
from apps.risk.engine import (
    classify_checkpoint,
    rank_routes,
    recommend_route,
    summarize_route,
)
from apps.risk.models import RiskLevel, RouteRiskSummary, WeatherSample


def sample(wind=0.0, rain=0.0, snow=0.0):
    return WeatherSample(wind_mph=wind, rain_in_per_hr=rain, snow_in_per_hr=snow)


class TestClassifyCheckpoint:
    def test_takes_worst_condition(self):
        # Low wind, moderate rain, severe snow -> overall SEVERE.
        risk = classify_checkpoint(sample(wind=10, rain=0.15, snow=2.5), load_lb=0)
        assert risk.level is RiskLevel.SEVERE
        assert "snow" in risk.drivers

    def test_all_calm_is_low(self):
        risk = classify_checkpoint(sample(), load_lb=20_000)
        assert risk.level is RiskLevel.LOW
        assert risk.is_passable

    def test_low_risk_has_no_drivers(self):
        # When everything is calm we don't surface noisy "drivers".
        risk = classify_checkpoint(sample(wind=10, rain=0.0, snow=0.0), load_lb=0)
        assert risk.level is RiskLevel.LOW
        assert risk.drivers == ()

    def test_load_escalation_marks_load_as_driver(self):
        # 50 mph wind + heavy load -> NO_TRAVEL, load is a driver.
        risk = classify_checkpoint(sample(wind=50), load_lb=35_000)
        assert risk.level is RiskLevel.NO_TRAVEL
        assert "load" in risk.drivers
        assert not risk.is_passable

    def test_breakdown_exposes_each_condition(self):
        risk = classify_checkpoint(sample(wind=36, rain=0.3, snow=0.0), load_lb=0)
        assert risk.by_condition["wind"] is RiskLevel.HIGH
        assert risk.by_condition["rain"] is RiskLevel.HIGH
        assert risk.by_condition["snow"] is RiskLevel.LOW
        assert set(risk.drivers) == {"wind", "rain"}


class TestSummarizeRoute:
    def test_distance_weighted_miles_and_average(self):
        levels = [RiskLevel.LOW, RiskLevel.HIGH, RiskLevel.SEVERE]
        miles = [10.0, 20.0, 5.0]
        s = summarize_route(levels, miles, travel_time_seconds=3600)
        assert s.total_miles == 35.0
        assert s.miles_at(RiskLevel.HIGH) == 20.0
        assert s.miles_at(RiskLevel.SEVERE) == 5.0
        # weighted avg = (0*10 + 2*20 + 3*5) / 35 = 55/35
        assert abs(s.average_risk - (55 / 35)) < 1e-9
        assert s.has_no_travel is False

    def test_detects_no_travel(self):
        s = summarize_route([RiskLevel.NO_TRAVEL], [12.0], travel_time_seconds=600)
        assert s.has_no_travel is True

    def test_length_mismatch_raises(self):
        import pytest

        with pytest.raises(ValueError):
            summarize_route([RiskLevel.LOW], [1.0, 2.0], travel_time_seconds=1)


def summ(no_travel=0.0, severe=0.0, high=0.0, avg=0.0, time=0.0, total=100.0):
    miles = {
        RiskLevel.NO_TRAVEL: no_travel,
        RiskLevel.SEVERE: severe,
        RiskLevel.HIGH: high,
    }
    return RouteRiskSummary(
        total_miles=total,
        travel_time_seconds=time,
        miles_by_level=miles,
        average_risk=avg,
        has_no_travel=no_travel > 0,
    )


class TestRanking:
    def test_fewest_severe_wins_first(self):
        a = summ(severe=10, high=0, time=100)   # more severe
        b = summ(severe=2, high=50, time=999)   # less severe but slower + more high
        assert rank_routes([a, b]) == [1, 0]

    def test_tiebreak_on_high_then_avg_then_time(self):
        a = summ(severe=5, high=10, avg=1.0, time=100)
        b = summ(severe=5, high=10, avg=1.0, time=90)   # identical but faster
        assert recommend_route([a, b]) == 1

    def test_high_breaks_severe_tie(self):
        a = summ(severe=5, high=30)
        b = summ(severe=5, high=10)
        assert recommend_route([a, b]) == 1

    def test_no_travel_route_is_deprioritized(self):
        passable = summ(no_travel=0, severe=40, high=40, time=9999)
        blocked = summ(no_travel=1, severe=0, high=0, time=10)
        # Even though 'blocked' is faster and lower severe, its No-Travel miles
        # push it last.
        assert recommend_route([passable, blocked]) == 0

    def test_empty_returns_none(self):
        assert recommend_route([]) is None
