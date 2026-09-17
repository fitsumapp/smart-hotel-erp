"""Orders transactional and business services."""
import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from hotel.integrity import record_stock_change
from hotel.models import MenuItem, Notification, Order, OrderItem, PaymentAttempt, RestaurantTable, SystemSettings
from users.models import User


TWOPLACES = Decimal("0.01")


def to_decimal(value):
    return Decimal(str(value or 0)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def get_tenant_frontend_base(request=None):
    if request:
        origin = request.META.get("HTTP_ORIGIN")
        if origin:
            return origin.rstrip("/")
        proto = "https" if request.is_secure() else "http"
        return f"{proto}://{request.get_host()}"
    return settings.FRONTEND_BASE_URL.rstrip("/")


def post_journal_entry(*args, **kwargs):
    from apps.finance.services import post_journal_entry as post
    return post(*args, **kwargs)

def get_system_settings():
    obj, _ = SystemSettings.objects.get_or_create(id=1)
    return obj


def calculate_order_financials(order, settings_obj=None):
    settings_obj = settings_obj or get_system_settings()
    sub_total = sum(
        (to_decimal(item.price_at_order) * item.quantity) for item in order.items.all()
    )
    service_amount = Decimal("0.00")
    if settings_obj.service_charge_enabled:
        service_amount = (
            sub_total * to_decimal(settings_obj.service_charge_percentage) / Decimal("100")
        ).quantize(TWOPLACES, rounding=ROUND_HALF_UP)

    vat_amount = Decimal("0.00")
    if settings_obj.vat_enabled:
        vat_amount = (
            sub_total * to_decimal(settings_obj.vat_percentage) / Decimal("100")
        ).quantize(TWOPLACES, rounding=ROUND_HALF_UP)

    grand_total = (sub_total + service_amount + vat_amount).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    return {
        "sub_total": sub_total,
        "service_charge": service_amount,
        "vat": vat_amount,
        "grand_total": grand_total,
    }


def sync_order_financials(order, settings_obj=None, save=True):
    settings_obj = settings_obj or get_system_settings()
    amounts = calculate_order_financials(order, settings_obj=settings_obj)
    order.sub_total = amounts["sub_total"]
    order.service_charge_amount = amounts["service_charge"]
    order.vat_amount = amounts["vat"]
    order.total_amount = amounts["grand_total"]
    order.service_charge_rate_snapshot = to_decimal(settings_obj.service_charge_percentage) if settings_obj.service_charge_enabled else Decimal("0")
    order.vat_rate_snapshot = to_decimal(settings_obj.vat_percentage) if settings_obj.vat_enabled else Decimal("0")
    if save:
        order.save(update_fields=["sub_total", "service_charge_amount", "vat_amount", "total_amount", "service_charge_rate_snapshot", "vat_rate_snapshot", "updated_at"])
    return amounts


def _order_fingerprint(table_id, items, waiter_id):
    normalized = sorted(
        [{"id": int(item["id"]), "quantity": int(item["quantity"])} for item in items],
        key=lambda value: (value["id"], value["quantity"]),
    )
    raw = json.dumps({"table_id": int(table_id), "items": normalized, "waiter_id": waiter_id}, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@transaction.atomic
def create_order_idempotently(*, table_id, items, waiter, idempotency_key=None):
    if idempotency_key and len(idempotency_key) > 120:
        raise ValidationError("Idempotency-Key must not exceed 120 characters.")
    if not items:
        raise ValidationError("At least one order item is required.")
    fingerprint = _order_fingerprint(table_id, items, waiter.id)
    if idempotency_key:
        existing = Order.objects.select_for_update().filter(idempotency_key=idempotency_key).first()
        if existing:
            if existing.idempotency_fingerprint != fingerprint:
                raise ValidationError("Idempotency key was already used for a different order request.")
            return existing, False
    table = RestaurantTable.objects.select_for_update().get(pk=table_id)
    order = Order.objects.create(
        table=table, waiter_id_ref=waiter.id, waiter_username=waiter.username,
        status="pending", payment_status="pending", idempotency_key=idempotency_key,
        idempotency_fingerprint=fingerprint,
    )
    for item in items:
        quantity = int(item["quantity"])
        if quantity <= 0:
            raise ValidationError("Order item quantity must be positive.")
        menu_item = MenuItem.objects.get(pk=item["id"], is_available=True)
        OrderItem.objects.create(order=order, menu_item=menu_item, quantity=quantity, price_at_order=menu_item.price)
    table.status = "occupied"
    table.save(update_fields=["status"])
    sync_order_financials(order)
    return order, True


def notify_users(users, message):
    """Create in-tenant Notification rows for a list of User objects."""
    payload = [Notification(user_id_ref=user.id, message=message) for user in users]
    if payload:
        Notification.objects.bulk_create(payload)


def notify_cashiers(message):
    """Notify all active cashiers in the current tenant."""
    cashiers = User.objects.filter(role="cashier", is_active=True)
    notify_users(cashiers, message)


def build_payment_summary(order, settings_obj=None):
    settings_obj = settings_obj or get_system_settings()
    totals = sync_order_financials(order, settings_obj=settings_obj, save=False)
    tip_amount = to_decimal(order.tip_amount)
    return {
        "order_id": order.id,
        "table_code": order.table.table_code if order.table else "",
        "sub_total": float(totals["sub_total"]),
        "service_charge": float(totals["service_charge"]),
        "vat": float(totals["vat"]),
        "grand_total": float(totals["grand_total"]),
        "tip_amount": float(tip_amount),
        "amount_due": float(
            (totals["grand_total"] + tip_amount).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        ),
        "currency": settings_obj.currency_symbol,
        "payment_status": order.payment_status,
        "payment_method": order.payment_method,
    }


def create_payment_page_url(order, request=None):
    frontend_base = get_tenant_frontend_base(request=request)
    order.ensure_payment_page_token()
    return f"{frontend_base}/pay/{order.payment_page_token}"


def generate_tx_ref(order):
    return f"order-{order.id}-{uuid4().hex[:10]}"


@transaction.atomic
def finalize_paid_order(order, payment_method, payment_reference=None, tip_amount=None, cashier=None, payment_attempt=None):
    order = Order.objects.select_for_update().select_related("table").prefetch_related("items__menu_item__ingredients_bom__ingredient").get(pk=order.pk)
    if order.payment_status == "paid":
        return order, False

    sync_order_financials(order)
    if tip_amount is not None:
        order.tip_amount = to_decimal(tip_amount)

    order.payment_status = "paid"
    order.payment_method = payment_method
    if payment_reference:
        order.payment_reference = payment_reference
    order.status = "paid"
    order.financials_finalized_at = timezone.now()
    if cashier:
        order.cashier_id_ref = cashier.id
    order.save()

    # --- Post General Ledger Journal Entry ---
    payment_entry = None
    try:
        pay_code = "1000" if payment_method == "Cash" else "1010"
        total = to_decimal(order.total_amount)
        subtotal = to_decimal(order.sub_total)
        vat = to_decimal(order.vat_amount)
        sc = to_decimal(order.service_charge_amount)

        jv_items = [
            {
                "account_code": pay_code,
                "debit": total,
                "credit": Decimal("0.00")
            }
        ]
        if subtotal > 0:
            jv_items.append({
                "account_code": "4100",
                "debit": Decimal("0.00"),
                "credit": subtotal
            })
        if vat > 0:
            jv_items.append({
                "account_code": "2200",
                "debit": Decimal("0.00"),
                "credit": vat
            })
        if sc > 0:
            jv_items.append({
                "account_code": "2300",
                "debit": Decimal("0.00"),
                "credit": sc
            })

        debit_sum = sum(x["debit"] for x in jv_items)
        credit_sum = sum(x["credit"] for x in jv_items)
        diff = debit_sum - credit_sum
        if diff != 0:
            for item in jv_items:
                if item["account_code"] == "4100":
                    item["credit"] += diff
                    break

        if len(jv_items) >= 2:
            payment_entry = post_journal_entry(
                description=f"Auto JV: F&B Order #{order.id} payment",
                items=jv_items
            )
    except Exception as e:
        if payment_attempt is not None:
            raise
        print(f"GL Auto-post error for Order #{order.id}: {e}")
    if payment_attempt is not None and payment_entry is not None:
        PaymentAttempt.objects.filter(pk=payment_attempt.pk, accounting_entry__isnull=True).update(accounting_entry=payment_entry)

    # Auto-deduct inventory ingredients based on Recipe BOM (with fail-safe)
    total_ingredient_cost = Decimal("0.00")
    try:
        for order_item in order.items.all():
            menu_item = order_item.menu_item
            for bom_item in menu_item.ingredients_bom.all():
                ingredient = bom_item.ingredient
                qty_to_deduct = bom_item.quantity_required * Decimal(str(order_item.quantity))
                locked_item, _ = record_stock_change(
                    item_id=ingredient.pk, transaction_type="sale_deduction",
                    quantity=qty_to_deduct, unit_cost=ingredient.unit_cost,
                    reference_number=f"ORD-{order.id}",
                    notes=f"Auto-deducted for menu item '{menu_item.name}' (qty: {order_item.quantity})",
                    logged_by_username=cashier.username if cashier else "system_auto",
                )
                total_ingredient_cost += qty_to_deduct * to_decimal(locked_item.unit_cost)
                
        if total_ingredient_cost > 0:
            post_journal_entry(
                description=f"Auto JV: COGS for Order #{order.id}",
                items=[
                    {
                        "account_code": "5000",
                        "debit": total_ingredient_cost,
                        "credit": Decimal("0.00")
                    },
                    {
                        "account_code": "1300",
                        "debit": Decimal("0.00"),
                        "credit": total_ingredient_cost
                    }
                ]
            )
    except Exception as e:
        raise ValueError(f"Inventory deduction failed for Order #{order.id}: {e}") from e

    if order.table:
        order.table.status = "available"
        order.table.save(update_fields=["status"])

    notify_cashiers(f"Order Paid - Print Receipt: Table {order.table.table_code} / ORD-{order.id}")
    return order, True


def get_public_order_from_token(token):
    try:
        return (
            Order.objects.prefetch_related("items__menu_item")
            .select_related("table")
            .get(payment_page_token=token)
        )
    except Order.DoesNotExist as exc:
        raise ValueError("Payment session not found.") from exc


