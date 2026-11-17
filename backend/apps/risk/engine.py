"""
Risk engine: turn weather + load into checkpoint risk, aggregate per route, and
rank routes using the spec's recommendation priority.

Pure functions only — no IO. Given the same inputs they always return the same
outputs, which is what makes the test suite meaningful.
"""
from __future__ import annotations

from .models import (
    CheckpointRisk,
    RiskLevel,
    RouteRiskSummary,
    WeatherSample,
)
from .rules import RAIN, SNOW, WIND, apply_load_rules


def classify_checkpoint(weather: WeatherSample, load_lb: float) -> CheckpointRisk:
    """Classify a single checkpoint.

    The overall level is the worst (max) of the wind (load-adjusted), rain and
    snow classifications. We keep the per-condition breakdown and record which
    condition(s) drove the final level so the UI can explain it.
    """
    base_wind = WIND.classify(weather.wind_mph)
    wind_level = apply_load_rules(weather.wind_mph, load_lb, base_wind)
    rain_level = RAIN.classify(weather.rain_in_per_hr)
    snow_level = SNOW.classify(weather.snow_in_per_hr)

    by_condition = {"wind": wind_level, "rain": rain_level, "snow": snow_level}
    # Flag load as a driver when it escalated wind beyond the raw wind reading.
    if wind_level > base_wind:
        by_condition["load"] = wind_level

    overall = max(by_condition.values())
    # "Drivers" only carry meaning above Low — when everything is calm, naming
    # every condition as a driver is just noise for the UI.
    if overall == RiskLevel.LOW:
        drivers: tuple[str, ...] = ()
    else:
        drivers = tuple(cond for cond, lvl in by_condition.items() if lvl == overall)
    return CheckpointRisk(level=overall, by_condition=by_condition, drivers=drivers)


def summarize_route(
    checkpoint_levels: list[RiskLevel],
    segment_miles: list[float],
    travel_time_seconds: float,
) -> RouteRiskSummary:
    """Aggregate per-checkpoint risk into a route-level summary.

    ``segment_miles[i]`` is the distance attributed to ``checkpoint_levels[i]``
    (the stretch of road that checkpoint represents). Distance-weighting makes
    "severe miles" and "average risk" reflect real road length rather than raw
    checkpoint counts.
    """
    if len(checkpoint_levels) != len(segment_miles):
        raise ValueError("checkpoint_levels and segment_miles must be the same length")

    total_miles = sum(segment_miles)
    miles_by_level: dict[RiskLevel, float] = {}
    weighted_risk = 0.0
    for level, miles in zip(checkpoint_levels, segment_miles):
        miles_by_level[level] = miles_by_level.get(level, 0.0) + miles
        weighted_risk += int(level) * miles

    average_risk = (weighted_risk / total_miles) if total_miles else 0.0

    return RouteRiskSummary(
        total_miles=total_miles,
        travel_time_seconds=travel_time_seconds,
        miles_by_level=miles_by_level,
        average_risk=average_risk,
        has_no_travel=miles_by_level.get(RiskLevel.NO_TRAVEL, 0.0) > 0,
    )


def recommendation_sort_key(summary: RouteRiskSummary) -> tuple:
    """Sort key implementing the spec's recommendation priority (ascending = better).

    Spec priority:
        1. Fewest Severe miles
        2. Fewest High miles
        3. Lowest average risk
        4. Shortest travel time

    Extension: a route with No-Travel miles is impassable, so No-Travel miles are
    the *first* (most important) key — a route you cannot legally drive can never
    be recommended over one you can. This strictly extends the spec; it never
    reorders two routes that both have zero No-Travel miles.
    """
    return (
        summary.miles_at(RiskLevel.NO_TRAVEL),
        summary.miles_at(RiskLevel.SEVERE),
        summary.miles_at(RiskLevel.HIGH),
        summary.average_risk,
        summary.travel_time_seconds,
    )


def rank_routes(summaries: list[RouteRiskSummary]) -> list[int]:
    """Return route indices ordered best-first per :func:`recommendation_sort_key`."""
    return sorted(range(len(summaries)), key=lambda i: recommendation_sort_key(summaries[i]))


def recommend_route(summaries: list[RouteRiskSummary]) -> int | None:
    """Return the index of the recommended route, or None if there are no routes."""
    ranking = rank_routes(summaries)
    return ranking[0] if ranking else None
