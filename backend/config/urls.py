from django.http import JsonResponse
from django.urls import include, path


def healthcheck(_request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("api/health/", healthcheck, name="health"),
    path("api/", include("apps.routing.api.urls")),
]
