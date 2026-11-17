"""
Request validation + response shaping for the plan endpoint.

The request is validated with a DRF serializer. The response is built with plain
functions from the planner's dataclasses — explicit and easy to evolve, with no
accidental field leakage.
"""
from __future__ import annotations

from django.conf import settings
from rest_framework import serializers

from apps.risk.models import RiskLevel
from apps.routing.services.planner import (
    CheckpointResult,
    Heatmap,
    PlanResult,
    RouteResult,
)


class PlanRequestSerializer(serializers.Serializer):
    origin = serializers.CharField(max_length=300)
    destination = serializers.CharField(max_length=300)
    departure = serializers.DateTimeField()
    load_lb = serializers.FloatField(min_value=0)
    interval_miles = serializers.ChoiceField(
        choices=settings.PLANNER["SAMPLING_INTERVALS_MILES"],
        required=False,
        default=settings.PLANNER["DEFAULT_SAMPLING_INTERVAL_MILES"],
    )
    alternatives = serializers.IntegerField(
        min_value=1, max_value=5, required=False, default=3
    )


# --------------------------------------------------------------------------- #
# Response builders
# --------------------------------------------------------------------------- #
def _risk_level_payload(level: RiskLevel) -> dict:
    return {"level": int(level), "label": level.label}


def serialize_checkpoint(cp: CheckpointResult) -> dict:
    return {
        "lat": round(cp.lat, 6),
        "lng": round(cp.lng, 6),
        "distance_miles": round(cp.distance_miles, 2),
        "eta": cp.eta.isoformat(),
        "weather": {
            "wind_mph": round(cp.weather.wind_mph, 1),
            "rain_in_per_hr": round(cp.weather.rain_in_per_hr, 3),
            "snow_in_per_hr": round(cp.weather.snow_in_per_hr, 3),
            "temperature_f": round(cp.weather.temperature_f, 1) if cp.weather.temperature_f is not None else None,
            "forecast_time": cp.weather.forecast_time_iso,
        },
        "risk": {
            **_risk_level_payload(cp.risk.level),
            "drivers": list(cp.risk.drivers),
            "by_condition": {k: int(v) for k, v in cp.risk.by_condition.items()},
        },
    }


def serialize_route(route: RouteResult) -> dict:
    s = route.summary
    return {
        "label": route.label,
        "is_recommended": route.is_recommended,
        "geometry": [[round(lat, 6), round(lng, 6)] for lat, lng in route.geometry],
        "distance_miles": round(route.distance_miles, 1),
        "duration_seconds": round(route.duration_seconds),
        "eta_arrival": route.eta_arrival.isoformat(),
        "summary": {
            "total_miles": round(s.total_miles, 1),
            "travel_time_seconds": round(s.travel_time_seconds),
            "average_risk": round(s.average_risk, 3),
            "has_no_travel": s.has_no_travel,
            "miles_by_level": {
                level.name.lower(): round(s.miles_at(level), 1)
                for level in RiskLevel
            },
        },
        "checkpoints": [serialize_checkpoint(cp) for cp in route.checkpoints],
    }


def serialize_heatmap(heatmap: Heatmap) -> dict:
    return {
        "times": [t.isoformat() for t in heatmap.times],
        "bbox": {
            "min_lat": heatmap.bbox[0],
            "min_lng": heatmap.bbox[1],
            "max_lat": heatmap.bbox[2],
            "max_lng": heatmap.bbox[3],
        },
        "cells": [
            {"lat": round(c.lat, 5), "lng": round(c.lng, 5), "risk_by_hour": c.risk_by_hour}
            for c in heatmap.cells
        ],
    }


def serialize_plan(plan: PlanResult) -> dict:
    return {
        "query": {
            "origin": {"label": plan.origin_label, "lat": plan.origin.lat, "lng": plan.origin.lng},
            "destination": {"label": plan.destination_label, "lat": plan.destination.lat, "lng": plan.destination.lng},
            "departure": plan.departure.isoformat(),
            "load_lb": plan.load_lb,
            "sampling_interval_miles": plan.sampling_interval_miles,
        },
        "recommended_index": plan.recommended_index,
        "routes": [serialize_route(r) for r in plan.routes],
        "heatmap": serialize_heatmap(plan.heatmap),
        "risk_legend": [
            {"level": int(level), "label": level.label} for level in RiskLevel
        ],
    }
