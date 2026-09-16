import time
import logging
from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from core.observability import metrics

logger = logging.getLogger("smart_hotel.alert")

@never_cache
def live(request):
    return JsonResponse({"status": "ok", "service": "smart-hotel-erp"})

@never_cache
def ready(request):
    started = time.perf_counter()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        metrics.observe("database_health_duration", (time.perf_counter() - started) * 1000)
        return JsonResponse({"status": "ready", "database": "ok", "release": settings.RELEASE_VERSION})
    except Exception:
        metrics.increment("database_health_failures_total")
        logger.critical("database_readiness_failed", extra={"event": {"release": settings.RELEASE_VERSION}})
        return JsonResponse({"status": "not_ready", "database": "unavailable", "release": settings.RELEASE_VERSION}, status=503)

class MetricsView(APIView):
    permission_classes = [IsAdminUser]
    def get(self, request):
        return Response({"release": settings.RELEASE_VERSION, "environment": settings.ENVIRONMENT, "metrics": metrics.snapshot()})
