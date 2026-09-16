"""Identity authentication, OTP, MFA, token, and audit services."""
import hashlib
import logging
import hmac
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken
from core.observability import metrics

from users.models import AuthenticationAttempt, SecurityAuditEvent, User


OTP_TTL = timedelta(minutes=10)
OTP_COOLDOWN = timedelta(seconds=60)
MFA_TTL = timedelta(minutes=5)
MAX_OTP_ATTEMPTS = 5
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_TIME = timedelta(minutes=15)
logger = logging.getLogger(__name__)

DUMMY_PASSWORD_HASH = make_password("not-a-real-user-password")


def _hash_value(value):
    key = settings.SECRET_KEY.encode("utf-8")
    return hmac.new(key, str(value or "").strip().lower().encode("utf-8"), hashlib.sha256).hexdigest()


def client_ip_hash(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
    return _hash_value(forwarded or request.META.get("REMOTE_ADDR", "unknown"))


def audit_security_event(*, action, request=None, actor=None, target=None, metadata=None):
    logger.warning(
        "security_event",
        extra={"event": {"action": action, "actor_id": getattr(actor, "pk", None), "target_id": getattr(target, "pk", None), "metadata": metadata or {}}},
    )
    return SecurityAuditEvent.objects.create(
        actor=actor, target_user=target, action=action,
        actor_role=getattr(actor, "role", "") or "",
        request_id=(request.headers.get("X-Request-ID", "")[:80] if request else ""),
        ip_hash=(client_ip_hash(request) if request else ""),
        safe_metadata=metadata or {},
    )


def _secure_code():
    return f"{secrets.randbelow(1_000_000):06d}"


@transaction.atomic
def issue_activation_otp(user, *, force=False):
    user = User.objects.select_for_update().get(pk=user.pk)
    now = timezone.now()
    if not force and user.otp_sent_at and now - user.otp_sent_at < OTP_COOLDOWN:
        raise ValidationError("Please wait before requesting another verification code.")
    code = _secure_code()
    user.otp_code = None
    user.otp_hash = make_password(code)
    user.otp_expires_at = now + OTP_TTL
    user.otp_attempts = 0
    user.otp_sent_at = now
    user.otp_used_at = None
    user.save(update_fields=["otp_code", "otp_hash", "otp_expires_at", "otp_attempts", "otp_sent_at", "otp_used_at"])
    return code


@transaction.atomic
def verify_activation_otp(*, email, code):
    user = User.objects.select_for_update().filter(email__iexact=str(email or "").strip()).first()
    if not user or not user.otp_hash:
        return None
    now = timezone.now()
    if user.otp_used_at or not user.otp_expires_at or now > user.otp_expires_at or user.otp_attempts >= MAX_OTP_ATTEMPTS:
        return None
    if not check_password(str(code or ""), user.otp_hash):
        user.otp_attempts = F("otp_attempts") + 1
        user.save(update_fields=["otp_attempts"])
        return None
    user.is_active = True
    user.otp_hash = ""
    user.otp_expires_at = None
    user.otp_used_at = now
    user.otp_attempts = 0
    user.role = User.CUSTOMER
    user.save(update_fields=["is_active", "otp_hash", "otp_expires_at", "otp_used_at", "otp_attempts", "role"])
    return user


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    refresh["token_version"] = user.token_version
    refresh["role"] = user.role
    return {"refresh": str(refresh), "access": str(refresh.access_token)}


@transaction.atomic
def authenticate_with_lockout(*, identifier, password, request):
    normalized = str(identifier or "").strip().lower()
    attempt, _ = AuthenticationAttempt.objects.select_for_update().get_or_create(
        identifier_hash=_hash_value(normalized), ip_hash=client_ip_hash(request)
    )
    now = timezone.now()
    if attempt.locked_until and now < attempt.locked_until:
        metrics.increment("login_locked_total")
        audit_security_event(action="login_locked", request=request, metadata={"reason": "rate_limit"})
        return None
    from django.db.models import Q
    user = User.objects.select_for_update().filter(Q(email__iexact=normalized) | Q(username__iexact=normalized)).first()
    password_valid = user.check_password(password) if user else check_password(password, DUMMY_PASSWORD_HASH)
    if not user or not password_valid or not user.is_active:
        attempt.failure_count += 1
        attempt.last_attempt_at = now
        if attempt.failure_count >= MAX_LOGIN_ATTEMPTS:
            attempt.locked_until = now + LOCKOUT_TIME
        attempt.save(update_fields=["failure_count", "last_attempt_at", "locked_until"])
        if user:
            user.failed_login_attempts = F("failed_login_attempts") + 1
            user.save(update_fields=["failed_login_attempts"])
        metrics.increment("login_failures_total")
        audit_security_event(action="login_failed", request=request, target=user, metadata={"reason": "invalid_credentials"})
        return None
    attempt.failure_count = 0
    attempt.locked_until = None
    attempt.last_attempt_at = now
    attempt.save(update_fields=["failure_count", "locked_until", "last_attempt_at"])
    user.failed_login_attempts = 0
    user.locked_until = None
    user.save(update_fields=["failed_login_attempts", "locked_until"])
    metrics.increment("login_success_total")
    audit_security_event(action="login_password_verified", request=request, target=user)
    return user


@transaction.atomic
def issue_mfa_code(user):
    user = User.objects.select_for_update().get(pk=user.pk)
    code = _secure_code()
    user.mfa_hash = make_password(code)
    user.mfa_expires_at = timezone.now() + MFA_TTL
    user.mfa_attempts = 0
    user.save(update_fields=["mfa_hash", "mfa_expires_at", "mfa_attempts"])
    return code


@transaction.atomic
def verify_mfa_code(*, identifier, code, request):
    from django.db.models import Q
    normalized = str(identifier or "").strip().lower()
    user = User.objects.select_for_update().filter(Q(email__iexact=normalized) | Q(username__iexact=normalized)).first()
    now = timezone.now()
    if not user or user.role not in {User.ADMIN, User.FINANCE} or not user.mfa_hash or not user.mfa_expires_at or now > user.mfa_expires_at or user.mfa_attempts >= MAX_OTP_ATTEMPTS:
        metrics.increment("otp_mfa_failures_total")
        audit_security_event(action="mfa_failed", request=request, target=user, metadata={"reason": "invalid_or_expired"})
        return None
    if not check_password(str(code or ""), user.mfa_hash):
        user.mfa_attempts = F("mfa_attempts") + 1
        user.save(update_fields=["mfa_attempts"])
        metrics.increment("otp_mfa_failures_total")
        audit_security_event(action="mfa_failed", request=request, target=user, metadata={"reason": "invalid_code"})
        return None
    user.mfa_hash = ""
    user.mfa_expires_at = None
    user.mfa_attempts = 0
    user.save(update_fields=["mfa_hash", "mfa_expires_at", "mfa_attempts"])
    audit_security_event(action="login_succeeded", request=request, target=user, metadata={"mfa": True})
    return user
