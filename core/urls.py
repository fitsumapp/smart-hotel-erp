"""
core/urls.py — Tenant URL config.
Served for every hotel subdomain (e.g. hotel1.hotelerp.acrmatech.com).
All hotel staff APIs are under /api/users/ (users app handles everything).
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.schemas import get_schema_view
from rest_framework.renderers import JSONOpenAPIRenderer
from core.schema import V1SchemaGenerator
from core.health import MetricsView, live, ready

urlpatterns = [
    path("health/live", live, name="health-live"),
    path("health/ready", ready, name="health-ready"),
    path("api/v1/ops/metrics/", MetricsView.as_view(), name="ops-metrics"),
    path("admin/", admin.site.urls),
    path("api/users/", include("users.urls")),
    path(
        "api/v1/schema/",
        get_schema_view(title="Smart Hotel ERP API", version="1.0.0", public=False, generator_class=V1SchemaGenerator, renderer_classes=[JSONOpenAPIRenderer]),
        name="openapi-schema",
    ),
    path("api/v1/", include("users.urls")),
    path("users/", include("users.urls")),  # Fallback for cPanel Passenger /api mount point
]

# Serve media and static files in development
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

handler500 = "core.views.custom_500_handler"
handler404 = "core.views.custom_404_handler"