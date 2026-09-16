"""Dependency-free request tracing, JSON logging and process metrics."""
from __future__ import annotations
import json, logging, re, threading, time, uuid
from django.db import connection
from collections import Counter
from contextvars import ContextVar
from datetime import datetime, timezone

request_context = ContextVar("request_context", default={})
_SENSITIVE = re.compile(r"password|passwd|secret|token|authorization|cookie|otp|pin|card|cvv|identity|passport|guest|email|phone|address|profile_picture|employee_name", re.I)

def safe_path(path):
    """Remove opaque identifiers that may be bearer tokens from logged paths."""
    parts = []
    for part in str(path or "").split("/"):
        parts.append("[id]" if len(part) >= 20 and re.fullmatch(r"[A-Za-z0-9._~-]+", part) else part)
    return "/".join(parts)[:500]

def redact(value, key=""):
    if _SENSITIVE.search(str(key)):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): redact(v, k) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    text = str(value)
    return text[:500] + ("..." if len(text) > 500 else "")

class JsonFormatter(logging.Formatter):
    def format(self, record):
        context = request_context.get({})
        payload = {"timestamp": datetime.now(timezone.utc).isoformat(), "level": record.levelname, "logger": record.name, "message": record.getMessage(), **{k: v for k, v in context.items() if k != "request"}}
        if hasattr(record, "event"):
            payload["event"] = redact(record.event)
        if record.exc_info:
            payload["exception_type"] = record.exc_info[0].__name__
        return json.dumps(payload, default=str, separators=(",", ":"))

class Metrics:
    def __init__(self):
        self._lock, self.started = threading.Lock(), time.monotonic()
        self.counters, self.duration_ms = Counter(), Counter()
    def increment(self, name, value=1):
        with self._lock:
            self.counters[name] += value
    def observe(self, name, value):
        with self._lock:
            self.counters[f"{name}_count"] += 1
            self.duration_ms[f"{name}_sum_ms"] += float(value)
    def snapshot(self):
        with self._lock:
            return {"uptime_seconds": round(time.monotonic() - self.started, 3), **dict(self.counters), **dict(self.duration_ms)}

metrics = Metrics()

class ObservabilityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.logger = logging.getLogger("smart_hotel.request")
    def __call__(self, request):
        incoming = request.headers.get("X-Request-ID", "")
        request_id = incoming[:80] if re.fullmatch(r"[A-Za-z0-9._:-]{1,80}", incoming) else uuid.uuid4().hex
        request.request_id = request_id
        started = time.perf_counter()
        token = request_context.set({"request": request, "request_id": request_id, "method": request.method, "path": safe_path(request.path)})
        status_code, response = 500, None
        query_count, query_duration = 0, 0.0

        def query_wrapper(execute, sql, params, many, context):
            nonlocal query_count, query_duration
            query_started = time.perf_counter()
            try:
                return execute(sql, params, many, context)
            except Exception:
                metrics.increment("database_query_errors_total")
                raise
            finally:
                elapsed = (time.perf_counter() - query_started) * 1000
                query_count += 1
                query_duration += elapsed
                if elapsed >= 500:
                    metrics.increment("database_slow_queries_total")

        try:
            with connection.execute_wrapper(query_wrapper):
                response = self.get_response(request)
            status_code = response.status_code
            return response
        finally:
            duration = round((time.perf_counter() - started) * 1000, 2)
            actor = getattr(request, "user", None)
            actor_id = getattr(actor, "pk", None) if getattr(actor, "is_authenticated", False) else None
            metrics.increment("http_requests_total")
            metrics.increment(f"http_status_{status_code}_total")
            metrics.observe("http_request_duration", duration)
            metrics.increment("database_queries_total", query_count)
            metrics.observe("database_query_duration", query_duration)
            if status_code >= 500:
                metrics.increment("http_errors_total")
            self.logger.info("request_completed", extra={"event": {"status": status_code, "duration_ms": duration, "actor_id": actor_id, "db_query_count": query_count, "db_duration_ms": round(query_duration, 2)}})
            if response is not None:
                response["X-Request-ID"] = request_id
            request_context.reset(token)
