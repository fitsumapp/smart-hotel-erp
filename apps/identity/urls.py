from django.urls import path
from rest_framework.routers import DefaultRouter
from .tokens import VersionedTokenRefreshView

from .views import LoginView, LogoutView, RegisterView, ResendOTPView, UserViewSet, VerifyMFAView, VerifyOTPView

router = DefaultRouter()
router.register(r"users", UserViewSet, basename="user")

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("verify-otp/", VerifyOTPView.as_view(), name="verify-otp"),
    path("resend-otp/", ResendOTPView.as_view(), name="resend-otp"),
    path("verify-mfa/", VerifyMFAView.as_view(), name="verify-mfa"),
    path("login/", LoginView.as_view(), name="login"),
    path("token/refresh/", VersionedTokenRefreshView.as_view(), name="token-refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
] + router.urls
