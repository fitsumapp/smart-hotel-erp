"""Custom HTTP error handlers masking stack traces and returning correlation IDs."""
import json
import logging
from django.http import HttpResponse

logger = logging.getLogger(__name__)


def custom_500_handler(request):
    """Generic 500 handler concealing tracebacks and returning a correlation ID."""
    request_id = getattr(request, "request_id", "")
    logger.error("Unhandled 500 server error", extra={"event": {"request_id": request_id, "path": request.path}})

    if request.path.startswith("/api/"):
        content = json.dumps({
            "error": {
                "code": "internal_error",
                "message": "An internal error occurred.",
                "correlation_id": request_id,
            }
        })
        return HttpResponse(content, content_type="application/json", status=500)

    html = (
        "<!DOCTYPE html><html><head><title>500 Internal Server Error</title>"
        "<style>body{font-family:sans-serif;text-align:center;padding:40px;background:#f8fafc;color:#1e293b;}"
        "h1{color:#e11d48;}</style></head><body>"
        "<h1>An Unexpected Error Occurred</h1>"
        "<p>Our team has been notified. Please try again later.</p>"
        f"<p><small>Correlation ID: {request_id}</small></p>"
        "</body></html>"
    )
    return HttpResponse(html, content_type="text/html", status=500)


def custom_404_handler(request, exception=None):
    """Generic 404 handler for unknown resources."""
    request_id = getattr(request, "request_id", "")

    if request.path.startswith("/api/"):
        content = json.dumps({
            "error": {
                "code": "not_found",
                "message": "The requested resource was not found.",
                "correlation_id": request_id,
            }
        })
        return HttpResponse(content, content_type="application/json", status=404)

    html = (
        "<!DOCTYPE html><html><head><title>404 Not Found</title>"
        "<style>body{font-family:sans-serif;text-align:center;padding:40px;background:#f8fafc;color:#1e293b;}</style></head><body>"
        "<h1>Resource Not Found</h1>"
        "<p>The requested page or endpoint does not exist.</p>"
        f"<p><small>Correlation ID: {request_id}</small></p>"
        "</body></html>"
    )
    return HttpResponse(html, content_type="text/html", status=404)
