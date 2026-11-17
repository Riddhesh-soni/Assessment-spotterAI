"""DRF exception handler that maps provider errors to clean HTTP responses."""
from __future__ import annotations

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from apps.providers.base import (
    GeocodingError,
    ProviderConfigError,
    ProviderError,
    UpstreamError,
)

# Map provider exception types to (HTTP status, stable error code).
_PROVIDER_STATUS = {
    ProviderConfigError: (status.HTTP_503_SERVICE_UNAVAILABLE, "provider_misconfigured"),
    GeocodingError: (status.HTTP_422_UNPROCESSABLE_ENTITY, "geocoding_failed"),
    UpstreamError: (status.HTTP_502_BAD_GATEWAY, "upstream_error"),
    ProviderError: (status.HTTP_502_BAD_GATEWAY, "provider_error"),
}


def custom_exception_handler(exc, context):
    # Let DRF handle validation/HTTP errors first.
    response = drf_exception_handler(exc, context)
    if response is not None:
        return response

    for exc_type, (http_status, code) in _PROVIDER_STATUS.items():
        if isinstance(exc, exc_type):
            return Response(
                {"error": {"code": code, "detail": str(exc)}}, status=http_status
            )
    return None  # fall through to Django's default 500 handling
