from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication


class VersionedJWTAuthentication(JWTAuthentication):
    """Reject tokens issued before password, role, or account-status changes."""

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if int(validated_token.get("token_version", 0)) != user.token_version:
            raise AuthenticationFailed("Session has been revoked.", code="session_revoked")
        if not user.is_active:
            raise AuthenticationFailed("Account is inactive.", code="user_inactive")
        return user
