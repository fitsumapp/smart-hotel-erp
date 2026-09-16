"""Backward-compatible aggregate of domain URL modules."""
from django.urls import include, path
# Initialize the compatibility facade before domain URL modules import views.
from . import views as _legacy_views  # noqa: F401


urlpatterns = [
    path("", include("apps.identity.urls")),
    path("", include("apps.rooms.urls")),
    path("", include("apps.reservations.urls")),
    path("", include("apps.orders.urls")),
    path("", include("apps.payments.urls")),
    path("", include("apps.inventory.urls")),
    path("", include("apps.finance.urls")),
    path("", include("apps.reporting.urls")),
    path("", include("apps.audit.urls")),
]
