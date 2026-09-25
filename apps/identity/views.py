"""Identity API views."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import transaction
from rest_framework import permissions, status, viewsets
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.response import Response
from rest_framework.views import APIView

from users.models import User
from users.permissions import IsHotelAdmin
from .serializers import PublicRegistrationSerializer, UserSerializer
from .services import (
    audit_security_event, authenticate_with_lockout, get_tokens_for_user,
    issue_activation_otp, issue_mfa_code, verify_activation_otp, verify_mfa_code,
)
from rest_framework_simplejwt.tokens import RefreshToken


def _send_code(*, subject, code, email):
    send_mail(subject, f"Your verification code is: {code}. It expires shortly.", settings.DEFAULT_FROM_EMAIL, [email])


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "login"

    def post(self, request):
        identifier = request.data.get("username") or request.data.get("email")
        password = request.data.get("password")
        if not identifier or not password:
            return Response({"error": "Invalid credentials or account unavailable."}, status=401)
        user = authenticate_with_lockout(identifier=identifier, password=password, request=request)
        if not user:
            return Response({"error": "Invalid credentials or account unavailable."}, status=401)
        enforce_mfa = settings.ENFORCE_EMAIL_MFA
        if enforce_mfa and (user.is_superuser or user.role in {User.ADMIN, User.FINANCE}):
            code = issue_mfa_code(user)
            try:
                _send_code(subject="Smart Hotel ERP login verification", code=code, email=user.email)
            except Exception:
                audit_security_event(action="mfa_delivery_failed", request=request, target=user)
                return Response({"error": "Unable to complete authentication."}, status=503)
            return Response({"message": "Additional verification required.", "mfa_required": True}, status=202)
        audit_security_event(action="login_succeeded", request=request, target=user, metadata={"mfa": False})
        return Response({"message": "Login successful.", "tokens": get_tokens_for_user(user), "user": UserSerializer(user).data})


class VerifyMFAView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "mfa"

    def post(self, request):
        user = verify_mfa_code(
            identifier=request.data.get("username") or request.data.get("email"),
            code=request.data.get("code"), request=request,
        )
        if not user:
            return Response({"error": "Invalid or expired verification code."}, status=400)
        return Response({"message": "Login successful.", "tokens": get_tokens_for_user(user), "user": UserSerializer(user).data})


class LogoutView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        raw_refresh = request.data.get("refresh")
        if not raw_refresh:
            return Response({"error": "Refresh token is required."}, status=400)
        with transaction.atomic():
            try:
                refresh = RefreshToken(raw_refresh)
                user = User.objects.select_for_update().get(pk=refresh["user_id"])
            except Exception as exc:
                raise AuthenticationFailed("Invalid refresh token.", code="token_not_valid") from exc
            if refresh.get("token_version") != user.token_version:
                raise AuthenticationFailed("Session has already been revoked.", code="session_revoked")
            refresh.blacklist()
            user.token_version += 1
            user.mfa_hash = ""
            user.mfa_expires_at = None
            user.save(update_fields=["token_version", "mfa_hash", "mfa_expires_at"])
            audit_security_event(action="logout", request=request, actor=user, target=user)
        return Response(status=204)


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "register"

    def post(self, request):
        serializer = PublicRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        code = issue_activation_otp(user, force=True)
        try:
            _send_code(subject="Smart Hotel ERP account verification", code=code, email=user.email)
        except Exception:
            audit_security_event(action="otp_delivery_failed", request=request, target=user)
            return Response({"error": "Registration created but verification delivery failed."}, status=503)
        audit_security_event(action="public_registration", request=request, target=user)
        return Response({"message": "Registration successful. Check your email.", "user": UserSerializer(user).data}, status=201)


class ResendOTPView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "otp"

    def post(self, request):
        user = User.objects.filter(email__iexact=str(request.data.get("email") or "").strip(), is_active=False).first()
        if user:
            try:
                code = issue_activation_otp(user)
                _send_code(subject="Smart Hotel ERP account verification", code=code, email=user.email)
                audit_security_event(action="otp_resent", request=request, target=user)
            except (ValidationError, Exception):
                pass
        return Response({"message": "If the account is eligible, a verification code has been sent."})


class VerifyOTPView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "otp"

    def post(self, request):
        user = verify_activation_otp(email=request.data.get("email"), code=request.data.get("otp"))
        if not user:
            return Response({"error": "Invalid or expired verification code."}, status=400)
        audit_security_event(action="account_activated", request=request, target=user)
        return Response({"message": "Account activated successfully!"})


class UserViewSet(viewsets.ModelViewSet):
    serializer_class = UserSerializer
    permission_classes = [IsHotelAdmin]

    def get_queryset(self):
        return User.objects.all().order_by("-id")

    def perform_create(self, serializer):
        user = serializer.save()
        audit_security_event(
            action="staff_account_created", request=self.request, actor=self.request.user,
            target=user, metadata={"role": user.role, "is_active": user.is_active},
        )

    def perform_update(self, serializer):
        with transaction.atomic():
            target = User.objects.select_for_update().get(pk=serializer.instance.pk)
        before = {"role": target.role, "is_active": target.is_active, "password": target.password}
        updated = serializer.save()
        sensitive_changed = (
            before["role"] != updated.role or before["is_active"] != updated.is_active
            or before["password"] != updated.password
        )
        if sensitive_changed:
            User.objects.filter(pk=updated.pk).update(token_version=updated.token_version + 1)
            updated.refresh_from_db()
        audit_security_event(
            action="staff_account_updated", request=self.request, actor=self.request.user,
            target=updated, metadata={
                "role_before": before["role"], "role_after": updated.role,
                "active_before": before["is_active"], "active_after": updated.is_active,
                "password_changed": before["password"] != updated.password,
                "sessions_revoked": sensitive_changed,
            },
        )

    def perform_destroy(self, instance):
        audit_security_event(action="staff_account_deleted", request=self.request, actor=self.request.user, target=instance)
        instance.is_active = False
        instance.token_version += 1
        instance.save(update_fields=["is_active", "token_version"])
