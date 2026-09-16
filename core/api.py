"""Shared API behavior: safe errors and bounded v1 pagination."""
import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler
from core.observability import metrics


logger = logging.getLogger(__name__)


def _message(data, fallback):
    if isinstance(data, dict):
        value = data.get("detail") or data.get("error")
        if isinstance(value, (str, int, float)):
            return str(value)
    if isinstance(data, list) and data:
        return str(data[0])
    return fallback


def api_exception_handler(exc, context):
    """Return one predictable envelope without disclosing internal exceptions."""
    if isinstance(exc, DjangoValidationError):
        exc = exc.messages
        return Response(
            {"error": {"code": "validation_error", "message": "Request validation failed.", "details": exc}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    response = drf_exception_handler(exc, context)
    if response is not None and response.status_code == status.HTTP_403_FORBIDDEN:
        metrics.increment("authorization_denials_total")
        request = context.get("request")
        logger.warning("authorization_denied", extra={"event": {"actor_id": getattr(getattr(request, "user", None), "pk", None), "view": context.get("view").__class__.__name__ if context.get("view") else ""}})
    if response is None:
        logger.exception("Unhandled API exception", exc_info=exc)
        req = context.get("request")
        req_id = getattr(req, "request_id", "") if req else ""
        return Response(
            {"error": {"code": "internal_error", "message": "An internal error occurred.", "correlation_id": req_id}},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    code = getattr(exc, "default_code", None) or "request_error"
    fallback = "Request could not be completed."
    response.data = {
        "error": {
            "code": str(code),
            "message": _message(response.data, fallback),
            "details": response.data,
        }
    }
    return response


class V1PageNumberPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 100

    def paginate_queryset(self, queryset, request, view=None):
        if not request.path.startswith("/api/v1/"):
            return None
        return super().paginate_queryset(queryset, request, view=view)
