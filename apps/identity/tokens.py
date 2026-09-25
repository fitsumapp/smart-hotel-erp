"""Serialize refresh rotation against logout and reject revoked sessions."""
from django.db import transaction
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.views import TokenRefreshView
from users.models import User


class VersionedTokenRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        with transaction.atomic():
            token = self.token_class(attrs["refresh"])
            user = User.objects.select_for_update().filter(pk=token.get("user_id")).first()
            if not user or not user.is_active or token.get("token_version") != user.token_version:
                raise AuthenticationFailed("Session has been revoked.", code="session_revoked")
            # Revalidate the blacklist after acquiring the user lock.
            return super().validate(attrs)


class VersionedTokenRefreshView(TokenRefreshView):
    serializer_class = VersionedTokenRefreshSerializer
    throttle_scope = "refresh"
