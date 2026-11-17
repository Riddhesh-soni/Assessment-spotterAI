"""
Domain models for the risk engine.

Deliberately free of Django / IO imports: this module is pure data + types so the
risk logic can be unit-tested in isolation and reused anywhere.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum


class RiskLevel(IntEnum):
    """
    Ordered risk classification. Integer values double as the severity weight
    used when averaging risk across a route (higher == worse).
    """

    LOW = 0
    MODERATE = 1
    HIGH = 2
    SEVERE = 3
    NO_TRAVEL = 4

    @property
    def label(self) -> str:
        return self.name.replace("_", " ").title()


# Which weather condition drove a checkpoint's classification.
Condition = str  # one of: "wind", "rain", "snow", "load"


@dataclass(frozen=True)
class WeatherSample:
    """Weather observed/forecast at a single checkpoint for the arrival time."""

    wind_mph: float
    rain_in_per_hr: float
    snow_in_per_hr: float
    # Optional descriptive fields (not used by the rules, handy for the UI).
    temperature_f: float | None = None
    forecast_time_iso: str | None = None


@dataclass(frozen=True)
class CheckpointRisk:
    """Risk outcome for one checkpoint."""

    level: RiskLevel
    # Per-condition breakdown so the UI can explain *why* a checkpoint is risky.
    by_condition: dict[Condition, RiskLevel]
    # The condition(s) responsible for the final (max) level.
    drivers: tuple[Condition, ...]

    @property
    def is_passable(self) -> bool:
        return self.level is not RiskLevel.NO_TRAVEL


@dataclass
class RouteRiskSummary:
    """Aggregated risk + scoring inputs for a whole route."""

    total_miles: float
    travel_time_seconds: float
    miles_by_level: dict[RiskLevel, float] = field(default_factory=dict)
    average_risk: float = 0.0
    has_no_travel: bool = False

    def miles_at(self, level: RiskLevel) -> float:
        return self.miles_by_level.get(level, 0.0)
