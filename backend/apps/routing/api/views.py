"""HTTP API for trip planning."""
from __future__ import annotations

from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from apps.providers import get_geocoder, get_router, get_weather
from apps.routing.services.planner import TripPlanner

from .serializers import PlanRequestSerializer, serialize_plan


@api_view(["POST"])
def plan_trip(request: Request) -> Response:
    """Plan a weather-aware trip.

    Request body:
        {
          "origin": "Denver, CO",
          "destination": "Salt Lake City, UT",
          "departure": "2026-11-18T08:00:00Z",
          "load_lb": 42000,
          "interval_miles": 25,      // optional: 10 | 25 | 50
          "alternatives": 3          // optional
        }
    """
    serializer = PlanRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    planner = TripPlanner(
        geocoder=get_geocoder(),
        router=get_router(),
        weather=get_weather(),
        forecast_horizon_hours=settings.PLANNER["FORECAST_HORIZON_HOURS"],
    )
    plan = planner.plan(
        origin=data["origin"],
        destination=data["destination"],
        departure=data["departure"],
        load_lb=data["load_lb"],
        interval_miles=data["interval_miles"],
        alternatives=data["alternatives"],
    )
    return Response(serialize_plan(plan))
