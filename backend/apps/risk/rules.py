"""
Weather risk thresholds and load rules, transcribed from the assessment spec.

Boundary semantics (important — the spec is not uniform):

    Wind   <25 | 25-34 | 35-44 | 45-54 | >=55      -> No-Travel boundary INCLUSIVE
    Rain   <0.10 | 0.10-0.25 | 0.25-0.50 | 0.50-1.00 | >1.00  -> No-Travel EXCLUSIVE
    Snow   <0.5 | 0.5-1.0 | 1.0-2.0 | 2.0-3.0 | >3.0          -> No-Travel EXCLUSIVE

Convention used for every band *except* the No-Travel boundary: the lower bound
is inclusive and the upper bound is exclusive (e.g. wind 25.0 -> Moderate,
35.0 -> High). The No-Travel boundary is inclusive for wind (">=55") and
exclusive for rain/snow (">1.00", ">3.0"), matching the spec wording exactly.
"""
from __future__ import annotations

from dataclasses import dataclass

from .models import RiskLevel


@dataclass(frozen=True)
class Thresholds:
    """
    Four ascending lower-bounds for Moderate, High, Severe and No-Travel.

    ``no_travel_inclusive`` controls whether a value *equal to* the No-Travel
    bound classifies as No-Travel (wind) or stays Severe (rain/snow).
    """

    moderate: float
    high: float
    severe: float
    no_travel: float
    no_travel_inclusive: bool

    def classify(self, value: float) -> RiskLevel:
        if value > self.no_travel or (self.no_travel_inclusive and value >= self.no_travel):
            return RiskLevel.NO_TRAVEL
        if value >= self.severe:
            return RiskLevel.SEVERE
        if value >= self.high:
            return RiskLevel.HIGH
        if value >= self.moderate:
            return RiskLevel.MODERATE
        return RiskLevel.LOW


WIND = Thresholds(moderate=25, high=35, severe=45, no_travel=55, no_travel_inclusive=True)
RAIN = Thresholds(moderate=0.10, high=0.25, severe=0.50, no_travel=1.00, no_travel_inclusive=False)
SNOW = Thresholds(moderate=0.5, high=1.0, severe=2.0, no_travel=3.0, no_travel_inclusive=False)


# ---------------------------------------------------------------------------
# Load rules — escalate the *wind* classification based on cargo weight.
#
#   >=55 mph                 -> No Travel for any load   (already No-Travel by WIND)
#   45-54 mph + >30,000 lb   -> No Travel
#   35-44 mph + >40,000 lb   -> Severe
#
# Encoded as ordered (predicate -> escalated level) rules; the first match wins.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class LoadRule:
    """Escalate wind risk to ``escalate_to`` when wind is in [wind_min, wind_max)
    and load exceeds ``load_over_lb``."""

    wind_min: float
    wind_max: float  # exclusive upper bound; use float("inf") for open-ended
    load_over_lb: float
    escalate_to: RiskLevel
    description: str


LOAD_RULES: tuple[LoadRule, ...] = (
    LoadRule(
        wind_min=55, wind_max=float("inf"), load_over_lb=-1,
        escalate_to=RiskLevel.NO_TRAVEL,
        description=">=55 mph -> No Travel for any load",
    ),
    LoadRule(
        wind_min=45, wind_max=55, load_over_lb=30_000,
        escalate_to=RiskLevel.NO_TRAVEL,
        description="45-54 mph + >30,000 lb -> No Travel",
    ),
    LoadRule(
        wind_min=35, wind_max=45, load_over_lb=40_000,
        escalate_to=RiskLevel.SEVERE,
        description="35-44 mph + >40,000 lb -> Severe",
    ),
)


def apply_load_rules(wind_mph: float, load_lb: float, base_wind_level: RiskLevel) -> RiskLevel:
    """Return the wind risk level after applying load escalation rules.

    Only ever escalates (takes the max of base and any matching rule), so a load
    rule can never *lower* risk.
    """
    level = base_wind_level
    for rule in LOAD_RULES:
        if rule.wind_min <= wind_mph < rule.wind_max and load_lb > rule.load_over_lb:
            level = max(level, rule.escalate_to)
    return level
