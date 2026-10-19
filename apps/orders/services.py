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
from hotel.models import DiningSession, MenuItem, Notification, Order, OrderItem, PaymentAttempt, RestaurantTable, SystemSettings
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
def create_order_idempotently(*, table_id, items, waiter, idempotency_key=None, session_id=None):
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
    if table.status == "reserved":
        raise ValidationError(f"Table '{table.table_code}' is currently reserved.")

    # Resolve or create active DiningSession
    session = None
    if session_id:
        try:
            session = DiningSession.objects.select_for_update().get(pk=session_id)
        except DiningSession.DoesNotExist:
            raise ValidationError(f"Dining session #{session_id} not found.")
        if session.table_id != table.id:
            raise ValidationError(
                f"Dining session #{session_id} belongs to table '{session.table.table_code}', not '{table.table_code}'."
            )
        if session.status != "active":
            raise ValidationError(f"Dining session #{session_id} is {session.status} and cannot accept new orders.")
    else:
        # Check for existing active session for this table
        session = DiningSession.objects.select_for_update().filter(table=table, status="active").first()
        if not session:
            session = DiningSession.objects.create(
                table=table,
                status="active",
                opened_by_id_ref=waiter.id,
                opened_by_username=waiter.username,
            )
            # Retroactively link any existing unassigned unpaid orders for this table to this session
            Order.objects.filter(table=table, payment_status="pending", session__isnull=True).update(session=session)

    order = Order.objects.create(
        table=table,
        session=session,
        waiter_id_ref=waiter.id,
        waiter_username=waiter.username,
        status="pending",
        payment_status="pending",
        idempotency_key=idempotency_key,
        idempotency_fingerprint=fingerprint,
    )
    for item in items:
        quantity = int(item["quantity"])
        try:
            menu_item = MenuItem.objects.get(pk=item["id"])
        except MenuItem.DoesNotExist:
            raise ValidationError(f"Menu item (ID {item.get('id')}) was not found or has been removed.")
        if not menu_item.is_available:
            raise ValidationError(f"'{menu_item.name}' is currently unavailable (አልቋል / አይገኝም). Please remove it from cart.")

        notes = str(item.get("notes") or "").strip()[:255]
        OrderItem.objects.create(
            order=order,
            menu_item=menu_item,
            quantity=quantity,
            price_at_order=menu_item.price,
            notes=notes,
            status="pending",
        )
    if table.status != "occupied":
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
    data = {
        "order_id": order.id,
        "session_id": order.session_id,
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
    if order.session_id and order.session:
        data["session_summary"] = build_session_payment_summary(order.session, settings_obj=settings_obj)
    return data


def create_payment_page_url(order, request=None):
    frontend_base = get_tenant_frontend_base(request=request)
    order.ensure_payment_page_token()
    return f"{frontend_base}/pay/{order.payment_page_token}"


def generate_tx_ref(order):
    return f"order-{order.id}-{uuid4().hex[:10]}"


@transaction.atomic
def finalize_paid_order(order, payment_method, payment_reference=None, tip_amount=None, cashier=None, payment_attempt=None, reservation=None):
    order = Order.objects.select_for_update().select_related("table").prefetch_related("items__menu_item__ingredients_bom__ingredient").get(pk=order.pk)
    if order.payment_status == "paid":
        return order, False

    sync_order_financials(order)
    if tip_amount is not None:
        order.tip_amount = to_decimal(tip_amount)

    # Handle Room Charge integration with Guest Folio
    is_room_charge = str(payment_method).lower() in ["room charge", "room_charge", "room"]
    if is_room_charge:
        payment_method = "Room Charge"
        if reservation is None and payment_reference and str(payment_reference).isdigit():
            from hotel.models import Reservation
            reservation = Reservation.objects.filter(id=int(payment_reference), status="checked_in").first()

        if reservation:
            from hotel.models import FolioCharge
            tbl = order.table.table_code if order.table else "Room Service"
            charge_total = to_decimal(order.total_amount) + to_decimal(order.tip_amount or 0)
            FolioCharge.objects.create(
                reservation=reservation,
                description=f"F&B Order #{order.id} ({tbl})",
                amount=charge_total,
                added_by=cashier.username if cashier else "POS",
            )
            room_num = getattr(getattr(reservation, "room", None), "room_number", "")
            payment_reference = f"Room {room_num} - {reservation.guest_name}".strip(" -")

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
        if is_room_charge:
            pay_code = "1200"  # Accounts Receivable / Guest Folio
        elif payment_method == "Cash":
            pay_code = "1000"
        else:
            pay_code = "1010"
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
        raise ValueError(f"Accounting posting failed for Order #{order.id}.") from e
    if payment_attempt is not None and payment_entry is not None:
        PaymentAttempt.objects.filter(pk=payment_attempt.pk, accounting_entry__isnull=True).update(accounting_entry=payment_entry)

    # Auto-deduct inventory ingredients based on Recipe BOM (with fail-safe)
    settings = None
    try:
        from users.models import SystemSettings
        settings = SystemSettings.get_settings()
    except Exception:
        pass

    if settings is None or getattr(settings, "module_inventory", True):
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
        session = order.session
        remaining_unpaid = False
        if session:
            remaining_unpaid = Order.objects.filter(
                session=session,
                payment_status="pending",
            ).exclude(pk=order.pk).exists()
        else:
            remaining_unpaid = Order.objects.filter(
                table=order.table,
                payment_status="pending",
            ).exclude(pk=order.pk).exists()

        if not remaining_unpaid:
            if session and session.status == "active":
                session.status = "closed"
                session.closed_at = timezone.now()
                session.closed_by_id_ref = cashier.id if cashier else None
                session.save(update_fields=["status", "closed_at", "closed_by_id_ref"])

            order.table.status = "available"
            order.table.save(update_fields=["status"])

    notify_cashiers(f"Order Paid - Print Receipt: Table {order.table.table_code} / ORD-{order.id}")
    return order, True


@transaction.atomic
def settle_dining_session(
    session,
    payment_method="Cash",
    payment_reference=None,
    tip_amount=None,
    cashier=None,
    reservation=None,
):
    """
    Settle all unpaid orders belonging to a dining session in one atomic transaction.
    """
    session = (
        DiningSession.objects.select_for_update()
        .select_related("table")
        .prefetch_related("orders")
        .get(pk=session.pk)
    )
    if session.status == "closed":
        raise ValidationError("Dining session is already closed.")

    unpaid_orders = list(
        session.orders.select_for_update()
        .filter(payment_status="pending")
        .exclude(status="cancelled")
        .order_by("created_at")
    )
    if not unpaid_orders:
        if session.orders.exclude(status="cancelled").filter(payment_status="paid").exists():
            session.status = "closed"
            session.closed_at = timezone.now()
            session.closed_by_id_ref = cashier.id if cashier else None
            session.save(update_fields=["status", "closed_at", "closed_by_id_ref"])
            if session.table:
                session.table.status = "available"
                session.table.save(update_fields=["status"])
            return session, []
        raise ValidationError("No orders to settle in this dining session.")

    settled_orders = []
    total_tip = to_decimal(tip_amount or 0)
    for idx, ord_obj in enumerate(unpaid_orders):
        order_tip = total_tip if idx == 0 else Decimal("0.00")
        ref = payment_reference or f"SESS-{session.id}-{ord_obj.id}"
        settled, _ = finalize_paid_order(
            ord_obj,
            payment_method=payment_method,
            payment_reference=ref,
            tip_amount=order_tip,
            cashier=cashier,
            reservation=reservation,
        )
        settled_orders.append(settled)

    session.refresh_from_db()
    if session.status != "closed":
        session.status = "closed"
        session.closed_at = timezone.now()
        session.closed_by_id_ref = cashier.id if cashier else None
        session.save(update_fields=["status", "closed_at", "closed_by_id_ref"])
    if session.table and session.table.status != "available":
        session.table.status = "available"
        session.table.save(update_fields=["status"])

    return session, settled_orders


def build_session_payment_summary(session, settings_obj=None):
    settings_obj = settings_obj or get_system_settings()
    orders = session.orders.exclude(status="cancelled").select_related("table")
    sub_total = Decimal("0.00")
    service_charge = Decimal("0.00")
    vat = Decimal("0.00")
    grand_total = Decimal("0.00")
    tip_amount = Decimal("0.00")

    paid_total = Decimal("0.00")
    unpaid_total = Decimal("0.00")

    for ord_obj in orders:
        totals = sync_order_financials(ord_obj, settings_obj=settings_obj, save=False)
        sub_total += to_decimal(totals["sub_total"])
        service_charge += to_decimal(totals["service_charge"])
        vat += to_decimal(totals["vat"])
        grand_total += to_decimal(totals["grand_total"])
        tip_amount += to_decimal(ord_obj.tip_amount)

        ord_total_with_tip = to_decimal(totals["grand_total"]) + to_decimal(ord_obj.tip_amount)
        if ord_obj.payment_status == "paid":
            paid_total += ord_total_with_tip
        else:
            unpaid_total += ord_total_with_tip

    all_paid = bool(orders) and all(o.payment_status == "paid" for o in orders)
    amount_due = (
        Decimal("0.00") if all_paid else unpaid_total.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    )

    return {
        "session_id": session.id,
        "table_code": session.table.table_code if session.table else "",
        "table_id": session.table_id,
        "rounds_count": orders.count(),
        "sub_total": float(sub_total),
        "service_charge": float(service_charge),
        "vat": float(vat),
        "grand_total": float(grand_total),
        "tip_amount": float(tip_amount),
        "paid_amount": float(paid_total),
        "outstanding_balance": float(amount_due),
        "amount_due": float(amount_due),
        "currency": settings_obj.currency_symbol,
        "session_status": session.status,
        "payment_status": "paid" if all_paid else "pending",
    }


def get_public_order_from_token(token):
    try:
        return (
            Order.objects.prefetch_related("items__menu_item")
            .select_related("table")
            .get(payment_page_token=token)
        )
    except Order.DoesNotExist as exc:
        raise ValueError("Payment session not found.") from exc


