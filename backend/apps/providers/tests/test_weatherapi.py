"""WeatherAPI provider parsing tests (HTTP mocked with `responses`)."""
from datetime import datetime, timedelta, timezone

import responses

from apps.providers import weather_cache
from apps.providers.base import GeoPoint
from apps.providers.weatherapi import WeatherAPIProvider

BASE = "https://api.weatherapi.com/v1"


def _hour(epoch, wind, precip_in, snow_cm, temp_f):
    return {
        "time_epoch": epoch,
        "wind_mph": wind,
        "precip_in": precip_in,
        "snow_cm": snow_cm,
        "temp_f": temp_f,
    }


def _payload(hours):
    return {"forecast": {"forecastday": [{"hour": hours}]}}


def setup_function():
    weather_cache._CACHE.clear()


@responses.activate
def test_parses_units_and_rain_snow_split():
    base_epoch = int(datetime(2026, 11, 19, 8, tzinfo=timezone.utc).timestamp())
    hours = [
        _hour(base_epoch, wind=12.0, precip_in=0.20, snow_cm=0.0, temp_f=45.0),       # rain
        _hour(base_epoch + 3600, wind=30.0, precip_in=0.10, snow_cm=2.54, temp_f=30.0),  # snow
    ]
    responses.add(responses.GET, f"{BASE}/forecast.json", json=_payload(hours), status=200)

    provider = WeatherAPIProvider(api_key="k", base_url=BASE, timeout=10)
    start = datetime(2026, 11, 19, 8, tzinfo=timezone.utc)
    [hw] = provider.forecast([GeoPoint(39.74, -104.98)], start, start + timedelta(hours=6))

    # Hour 0: rain, no snow.
    assert hw.wind_mph[0] == 12.0
    assert hw.rain_in_per_hr[0] == 0.20
    assert hw.snow_in_per_hr[0] == 0.0
    # Hour 1: snowing -> snow converted cm->inch (2.54cm = 1in), rain suppressed.
    assert abs(hw.snow_in_per_hr[1] - 1.0) < 1e-9
    assert hw.rain_in_per_hr[1] == 0.0
    # Times are tz-aware UTC and align with the epochs.
    assert hw.times[0] == start
    assert hw.times[0].tzinfo is timezone.utc


@responses.activate
def test_second_call_is_cached_no_http():
    base_epoch = int(datetime(2026, 11, 19, 8, tzinfo=timezone.utc).timestamp())
    responses.add(
        responses.GET, f"{BASE}/forecast.json",
        json=_payload([_hour(base_epoch, 5.0, 0.0, 0.0, 50.0)]), status=200,
    )
    provider = WeatherAPIProvider(api_key="k", base_url=BASE, timeout=10)
    start = datetime(2026, 11, 19, 8, tzinfo=timezone.utc)
    pts = [GeoPoint(39.74, -104.98)]
    provider.forecast(pts, start, start + timedelta(hours=6))
    provider.forecast(pts, start, start + timedelta(hours=6))  # should hit cache
    # Only one upstream request despite two forecast() calls.
    assert len(responses.calls) == 1


def test_missing_key_raises():
    import pytest

    from apps.providers.base import ProviderConfigError

    provider = WeatherAPIProvider(api_key="", base_url=BASE, timeout=10)
    with pytest.raises(ProviderConfigError):
        provider.forecast([GeoPoint(1, 2)], datetime.now(timezone.utc), datetime.now(timezone.utc))
