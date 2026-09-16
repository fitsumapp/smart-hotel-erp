from django.urls import path

from .views import ChapaWebhookView, PublicInitiateChapaPaymentView, PublicPaymentDetailView, PublicVerifyChapaPaymentView

urlpatterns = [
    path("payments/public/<str:token>/", PublicPaymentDetailView.as_view(), name="public-payment-detail"),
    path("payments/public/<str:token>/initiate/", PublicInitiateChapaPaymentView.as_view(), name="public-payment-initiate"),
    path("payments/public/<str:token>/verify/", PublicVerifyChapaPaymentView.as_view(), name="public-payment-verify"),
    path("payments/chapa/webhook/", ChapaWebhookView.as_view(), name="chapa-webhook"),
]
