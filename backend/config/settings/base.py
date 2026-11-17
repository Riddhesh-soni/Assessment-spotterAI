"""
Base settings shared across all environments.

Environment-specific overrides live in dev.py / prod.py and are selected via
the DJANGO_SETTINGS_MODULE env var (defaults to config.settings.dev in manage.py).
"""
from pathlib import Path

import environ

# backend/ (two levels up from this file: config/settings/base.py)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["*"]),
    CORS_ALLOWED_ORIGINS=(list, ["http://localhost:5173"]),
)

# Load backend/.env if present (local dev); in prod we rely on real env vars.
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY", default="insecure-dev-key-change-me")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",  # required by DRF's default auth/permission machinery
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "corsheaders",
    # Local
    "apps.routing",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    },
]

# This app is stateless (no persistence required by the spec), but Django wants
# a default DB configured. SQLite keeps local setup zero-config.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    # This is a public, read-only planning API — no auth required.
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "EXCEPTION_HANDLER": "apps.routing.api.exceptions.custom_exception_handler",
}

CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")

# ---------------------------------------------------------------------------
# External provider configuration (see apps/providers).
# Keys are read from the environment so providers stay swappable & secret-free.
# ---------------------------------------------------------------------------
PROVIDERS = {
    "ROUTING": {
        "ORS_API_KEY": env("ORS_API_KEY", default=""),
        "ORS_BASE_URL": env(
            "ORS_BASE_URL", default="https://api.openrouteservice.org"
        ),
    },
    "GEOCODING": {
        "NOMINATIM_BASE_URL": env(
            "NOMINATIM_BASE_URL", default="https://nominatim.openstreetmap.org"
        ),
        "USER_AGENT": env(
            "GEOCODER_USER_AGENT", default="weather-aware-routing/1.0"
        ),
    },
    "WEATHER": {
        "OPEN_METEO_BASE_URL": env(
            "OPEN_METEO_BASE_URL", default="https://api.open-meteo.com/v1"
        ),
    },
    "HTTP_TIMEOUT": env.int("PROVIDER_HTTP_TIMEOUT", default=15),
}

# Planner tuning (kept in settings so behaviour is configurable per-env).
PLANNER = {
    # Checkpoint sampling intervals offered to the client (miles).
    "SAMPLING_INTERVALS_MILES": [10, 25, 50],
    "DEFAULT_SAMPLING_INTERVAL_MILES": env.int("DEFAULT_SAMPLING_MILES", default=25),
    "FORECAST_HORIZON_HOURS": 48,
}
