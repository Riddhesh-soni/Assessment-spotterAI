"""Threshold + load-rule tests. Boundary values are called out explicitly."""
import pytest

from apps.risk.models import RiskLevel
from apps.risk.rules import RAIN, SNOW, WIND, apply_load_rules


class TestWindThresholds:
    @pytest.mark.parametrize(
        "mph,expected",
        [
            (0, RiskLevel.LOW),
            (24.9, RiskLevel.LOW),
            (25, RiskLevel.MODERATE),       # lower bound inclusive
            (34, RiskLevel.MODERATE),
            (34.9, RiskLevel.MODERATE),
            (35, RiskLevel.HIGH),
            (44.9, RiskLevel.HIGH),
            (45, RiskLevel.SEVERE),
            (54.9, RiskLevel.SEVERE),
            (55, RiskLevel.NO_TRAVEL),       # >=55 inclusive per spec
            (80, RiskLevel.NO_TRAVEL),
        ],
    )
    def test_classify(self, mph, expected):
        assert WIND.classify(mph) is expected


class TestRainThresholds:
    @pytest.mark.parametrize(
        "rate,expected",
        [
            (0.0, RiskLevel.LOW),
            (0.09, RiskLevel.LOW),
            (0.10, RiskLevel.MODERATE),
            (0.24, RiskLevel.MODERATE),
            (0.25, RiskLevel.HIGH),
            (0.49, RiskLevel.HIGH),
            (0.50, RiskLevel.SEVERE),
            (1.00, RiskLevel.SEVERE),        # >1.00 exclusive -> 1.00 stays Severe
            (1.01, RiskLevel.NO_TRAVEL),
        ],
    )
    def test_classify(self, rate, expected):
        assert RAIN.classify(rate) is expected


class TestSnowThresholds:
    @pytest.mark.parametrize(
        "rate,expected",
        [
            (0.0, RiskLevel.LOW),
            (0.49, RiskLevel.LOW),
            (0.5, RiskLevel.MODERATE),
            (1.0, RiskLevel.HIGH),
            (2.0, RiskLevel.SEVERE),
            (3.0, RiskLevel.SEVERE),         # >3.0 exclusive -> 3.0 stays Severe
            (3.01, RiskLevel.NO_TRAVEL),
        ],
    )
    def test_classify(self, rate, expected):
        assert SNOW.classify(rate) is expected


class TestLoadRules:
    def test_high_wind_no_travel_any_load(self):
        # >=55 mph is No Travel regardless of load (even zero).
        base = WIND.classify(60)
        assert apply_load_rules(60, 0, base) is RiskLevel.NO_TRAVEL

    def test_severe_wind_heavy_load_escalates_to_no_travel(self):
        base = WIND.classify(50)  # SEVERE
        assert apply_load_rules(50, 35_000, base) is RiskLevel.NO_TRAVEL

    def test_severe_wind_light_load_stays_severe(self):
        base = WIND.classify(50)
        assert apply_load_rules(50, 30_000, base) is RiskLevel.SEVERE  # not >30k

    def test_severe_wind_boundary_load_not_over(self):
        # Exactly 30,000 lb is NOT ">30,000".
        base = WIND.classify(45)
        assert apply_load_rules(45, 30_000, base) is RiskLevel.SEVERE

    def test_high_wind_very_heavy_load_escalates_to_severe(self):
        base = WIND.classify(40)  # HIGH
        assert apply_load_rules(40, 45_000, base) is RiskLevel.SEVERE

    def test_high_wind_moderate_load_stays_high(self):
        base = WIND.classify(40)
        assert apply_load_rules(40, 40_000, base) is RiskLevel.HIGH  # not >40k

    def test_load_rules_never_lower_risk(self):
        # Low wind, huge load -> no escalation, stays LOW.
        base = WIND.classify(10)
        assert apply_load_rules(10, 80_000, base) is RiskLevel.LOW
