"""
core/urls.py — Tenant URL config.
Served for every hotel subdomain (e.g. hotel1.hotelerp.acrmatech.com).
All hotel staff APIs are under /api/users/ (users app handles everything).
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/users/", include("users.urls")),
]

# Serve media files in both dev and production
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)