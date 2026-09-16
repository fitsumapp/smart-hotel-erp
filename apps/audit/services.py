"""Append-only business audit write boundary."""
import hashlib
import ipaddress

from core.observability import redact, request_context, safe_path
from hotel.models import AuditEvent

def _request_details():
    request = request_context.get({}).get("request")
    if request is None:
        return None, "", None, {}
    user = getattr(request, "user", None)
    actor = user if getattr(user, "is_authenticated", False) else None
    raw_ip = request.META.get("REMOTE_ADDR", "")
    try:
        source_ip = str(ipaddress.ip_address(raw_ip)) if raw_ip else None
    except ValueError:
        source_ip = None
    user_agent = request.META.get("HTTP_USER_AGENT", "")[:500]
    client = {
        "method": request.method,
        "path": safe_path(request.path),
        "user_agent_hash": hashlib.sha256(user_agent.encode()).hexdigest() if user_agent else "",
    }
    return actor, getattr(request, "request_id", ""), source_ip, client

def record_audit_event(*, action, entity_type, entity_id, before=None, after=None, reason=""):
    actor, request_id, source_ip, client = _request_details()
    return AuditEvent.objects.create(
        actor=actor,
        actor_role=getattr(actor, "role", "") if actor else "",
        action=str(action)[:100],
        entity_type=str(entity_type)[:100],
        entity_id=str(entity_id)[:100],
        before_summary=redact(before or {}),
        after_summary=redact(after or {}),
        request_id=request_id[:80],
        source_ip=source_ip,
        client_metadata=client,
        reason=str(reason or "")[:255],
    )
