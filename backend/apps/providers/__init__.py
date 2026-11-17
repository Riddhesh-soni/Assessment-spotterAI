"""
Provider factory.

The rest of the codebase asks for a provider by role (geocoder / router /
weather) and receives something satisfying the matching Protocol in ``base``.
This is the *only* module that names concrete vendors, so changing a vendor is a
localised edit here.
"""
from __future__ import annotations

from django.conf import settings

from .base import GeocodingProvider, RoutingProvider, WeatherProvider
from .geocoding import NominatimGeocoder
from .routing import OpenRouteServiceProvider
from .weather import OpenMeteoProvider


def get_geocoder() -> GeocodingProvider:
    cfg = settings.PROVIDERS["GEOCODING"]
    return NominatimGeocoder(
        base_url=cfg["NOMINATIM_BASE_URL"],
        user_agent=cfg["USER_AGENT"],
        timeout=settings.PROVIDERS["HTTP_TIMEOUT"],
    )


def get_router() -> RoutingProvider:
    cfg = settings.PROVIDERS["ROUTING"]
    return OpenRouteServiceProvider(
        api_key=cfg["ORS_API_KEY"],
        base_url=cfg["ORS_BASE_URL"],
        timeout=settings.PROVIDERS["HTTP_TIMEOUT"],
    )


def get_weather() -> WeatherProvider:
    cfg = settings.PROVIDERS["WEATHER"]
    return OpenMeteoProvider(
        base_url=cfg["OPEN_METEO_BASE_URL"],
        timeout=settings.PROVIDERS["HTTP_TIMEOUT"],
    )
