from rest_framework import serializers

from hotel.models import PaymentAttempt


class PaymentAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentAttempt
        fields = [
            "id", "provider", "purpose", "order", "reservation", "expected_amount",
            "currency", "provider_tx_ref", "idempotency_key", "status",
            "provider_event_ref", "verified_at", "safe_metadata", "accounting_entry",
            "last_reconciled_at", "reconciliation_status", "created_at", "updated_at",
        ]
        read_only_fields = fields
