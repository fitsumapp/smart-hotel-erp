import json
import random
import hashlib
import hmac
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from urllib import error as urllib_error
from urllib import request as urllib_request
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import logout as django_logout
from django.core.mail import send_mail
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.db import connection

from rest_framework import permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

# Shared (public schema) model
from .models import User

# Tenant (hotel schema) models
from hotel.models import (
    Category,
    MenuItem,
    Notification,
    Order,
    OrderItem,
    Reservation,
    RestaurantTable,
    Room,
    SystemSettings,
    MaintenanceLog,
    RoomHistory,
    GuestProfile,
    FolioCharge,
    DayAuditLog,
)

from .serializers import (
    CategorySerializer,
    MenuItemSerializer,
    NotificationSerializer,
    MaintenanceLogSerializer,
    RoomHistorySerializer,
    GuestProfileSerializer,
    FolioChargeSerializer,
    DayAuditLogSerializer,
    OrderSerializer,
    ReservationSerializer,
    RestaurantTableSerializer,
    RoomSerializer,
    SystemSettingsSerializer,
    UserSerializer,
)


TWOPLACES = Decimal("0.01")


def to_decimal(value):
    return Decimal(str(value or 0)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def get_tenant_frontend_base(request=None, tenant_schema=None):
    from tenants.models import Domain

    if request:
        host = request.get_host().split(":")[0]
        if host not in {"localhost", "127.0.0.1"}:
            return f"http://{host}:3000".rstrip("/")

    schema_name = tenant_schema or connection.schema_name
    if schema_name and schema_name != "public":
        domain_obj = Domain.objects.filter(tenant__schema_name=schema_name, is_primary=True).select_related("tenant").first()
        if domain_obj:
            return f"http://{domain_obj.domain}:3000".rstrip("/")

    return settings.FRONTEND_BASE_URL.rstrip("/")


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {"refresh": str(refresh), "access": str(refresh.access_token)}


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
    taxable_amount = sub_total + service_amount
    if settings_obj.vat_enabled:
        vat_amount = (
            taxable_amount * to_decimal(settings_obj.vat_percentage) / Decimal("100")
        ).quantize(TWOPLACES, rounding=ROUND_HALF_UP)

    grand_total = (taxable_amount + vat_amount).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    return {
        "sub_total": sub_total,
        "service_charge": service_amount,
        "vat": vat_amount,
        "grand_total": grand_total,
    }


def sync_order_financials(order, settings_obj=None, save=True):
    amounts = calculate_order_financials(order, settings_obj=settings_obj)
    order.sub_total = amounts["sub_total"]
    order.service_charge_amount = amounts["service_charge"]
    order.vat_amount = amounts["vat"]
    order.total_amount = amounts["grand_total"]
    if save:
        order.save(update_fields=["sub_total", "service_charge_amount", "vat_amount", "total_amount", "updated_at"])
    return amounts


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


def chapa_request(path, payload=None, method="POST"):
    secret_key = settings.CHAPA_SECRET_KEY
    if not secret_key:
        raise ValueError("CHAPA_SECRET_KEY is not configured.")

    headers = {
        "Authorization": f"Bearer {secret_key}",
        "Content-Type": "application/json",
    }
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib_request.Request(
        f"{settings.CHAPA_BASE_URL.rstrip('/')}/{path.lstrip('/')}",
        data=body,
        headers=headers,
        method=method,
    )
    try:
        with urllib_request.urlopen(req, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib_error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise ValueError(detail or str(exc)) from exc
    except urllib_error.URLError as exc:
        raise ValueError(str(exc)) from exc


def verify_chapa_transaction(tx_ref):
    return chapa_request(f"transaction/verify/{tx_ref}", payload=None, method="GET")


def is_valid_chapa_signature(request):
    secret = settings.CHAPA_WEBHOOK_SECRET or settings.CHAPA_SECRET_KEY
    if not secret:
        return False
    raw_body = request.body or b""
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    signature = request.headers.get("chapa-signature") or request.headers.get("Chapa-Signature")
    payload_signature = request.headers.get("x-chapa-signature")
    return any(
        candidate and hmac.compare_digest(candidate, expected)
        for candidate in [signature, payload_signature]
    )


def generate_tx_ref(order):
    return f"order-{order.id}-{uuid4().hex[:10]}"


def finalize_paid_order(order, payment_method, payment_reference=None, tip_amount=None, cashier=None):
    sync_order_financials(order)
    if tip_amount is not None:
        order.tip_amount = to_decimal(tip_amount)

    order.payment_status = "paid"
    order.payment_method = payment_method
    if payment_reference:
        order.payment_reference = payment_reference
    order.status = "paid"
    if cashier:
        order.cashier_id_ref = cashier.id
    order.save()

    if order.table:
        order.table.status = "available"
        order.table.save(update_fields=["status"])

    notify_cashiers(f"Order Paid - Print Receipt: Table {order.table.table_code} / ORD-{order.id}")


def get_public_order_from_token(token):
    try:
        return (
            Order.objects.prefetch_related("items__menu_item")
            .select_related("table")
            .get(payment_page_token=token)
        )
    except Order.DoesNotExist as exc:
        raise ValueError("Payment session not found.") from exc


def create_public_reservation_url(reservation, request=None):
    frontend_base = get_tenant_frontend_base(request=request)
    reservation.ensure_tokens()
    return f"{frontend_base}/booking/{reservation.public_token}"


def get_public_reservation_from_token(token):
    try:
        return Reservation.objects.select_related("room").get(public_token=token)
    except Reservation.DoesNotExist as exc:
        raise ValueError("Reservation session not found.") from exc


def reservation_overlaps(room, check_in_date, check_out_date, exclude_id=None):
    qs = Reservation.objects.filter(
        room=room,
        status__in=["pending", "confirmed", "checked_in"],
        check_in_date__lt=check_out_date,
        check_out_date__gt=check_in_date,
    )
    if exclude_id:
        qs = qs.exclude(id=exclude_id)
    return qs.exists()


def calculate_reservation_amounts(room, check_in_date, check_out_date):
    nights = max((check_out_date - check_in_date).days, room.min_stay or 1)
    total_amount = (to_decimal(room.base_price) * nights).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    deposit_base = to_decimal(room.advance_payment_amount)
    if room.online_deposit_type == "Percentage":
        deposit_amount = (total_amount * deposit_base / Decimal("100")).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    else:
        deposit_amount = deposit_base
    if deposit_amount <= Decimal("0.00"):
        deposit_amount = total_amount
    if deposit_amount > total_amount:
        deposit_amount = total_amount
    return nights, total_amount, deposit_amount


def build_reservation_summary(reservation):
    return {
        "id": reservation.id,
        "room_id": reservation.room_id,
        "room_name": reservation.room.name,
        "room_number": reservation.room.room_number,
        "room_type": reservation.room.room_type,
        "room_image": reservation.room.main_image.url if reservation.room.main_image else None,
        "guest_name": reservation.guest_name,
        "guest_email": reservation.guest_email,
        "guest_phone": reservation.guest_phone,
        "check_in_date": reservation.check_in_date.isoformat(),
        "check_out_date": reservation.check_out_date.isoformat(),
        "adults": reservation.adults,
        "children": reservation.children,
        "status": reservation.status,
        "source": reservation.source,
        "payment_status": reservation.payment_status,
        "total_amount": float(reservation.total_amount),
        "deposit_amount": float(reservation.deposit_amount),
        "confirmation_code": reservation.confirmation_code,
        "qr_token": reservation.qr_token,
        "public_token": reservation.public_token,
        "payment_reference": reservation.payment_reference,
        "paid_at": reservation.paid_at.isoformat() if reservation.paid_at else None,
    }


def send_reservation_confirmation(reservation):
    summary = build_reservation_summary(reservation)
    qr_url = f"{get_tenant_frontend_base(tenant_schema=connection.schema_name)}/booking/{reservation.public_token}"
    message = (
        f"Reservation confirmed for Room {reservation.room.room_number}. "
        f"Code: {reservation.confirmation_code}. "
        f"Check-in: {reservation.check_in_date.isoformat()} "
        f"Check-out: {reservation.check_out_date.isoformat()}. "
        f"QR page: {qr_url}"
    )
    if reservation.guest_email:
        try:
            send_mail(
                subject=f"Booking Confirmation - Room {reservation.room.room_number}",
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[reservation.guest_email],
                fail_silently=True,
            )
        except Exception:
            pass
    summary["confirmation_delivery"] = {
        "email_sent": bool(reservation.guest_email),
        "sms_preview": message,
        "qr_url": qr_url,
    }
    return summary


def finalize_paid_reservation(reservation, payment_reference=None):
    reservation.ensure_tokens()
    reservation.payment_status = "paid"
    reservation.status = "confirmed"
    reservation.payment_reference = payment_reference or reservation.payment_reference
    reservation.paid_at = timezone.now()
    reservation.save(
        update_fields=[
            "confirmation_code", "qr_token", "public_token",
            "payment_status", "status", "payment_reference", "paid_at", "updated_at",
        ]
    )
    reservation.room.status = "Reserved"
    reservation.room.booking_source = "online" if reservation.source == "public" else "front_desk"
    reservation.room.save(update_fields=["status", "booking_source"])
    return send_reservation_confirmation(reservation)


# ── Status priority for waiter order list ─────────────────────────────────────
_WAITER_STATUS_PRIORITY = {
    "ready": 0,
    "pending": 1,
    "preparing": 2,
    "served": 3,
    "bill_requested": 4,
}


# ─────────────────────────────────────────────────────────────────────────────
# Auth Views
# ─────────────────────────────────────────────────────────────────────────────

class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        django_logout(request)
        email = request.data.get("username")
        password = request.data.get("password")

        if not email or not password:
            return Response({"error": "Please provide both email and password."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            from django.db.models import Q
            user = User.objects.get(Q(email=email) | Q(username=email))
            if user.check_password(password):
                if not user.is_active:
                    return Response(
                        {"error": "Account not activated. Please verify email."},
                        status=status.HTTP_401_UNAUTHORIZED,
                    )

                # Tenant isolation check: non-admin user must match current schema
                if not user.is_platform_admin and not user.is_superuser:
                    try:
                        from django.db import connection
                        from tenants.models import Hotel
                        current_schema = connection.schema_name
                        
                        # Check hotel activity
                        hotel = Hotel.objects.filter(schema_name=user.tenant_schema).first()
                        if hotel and not hotel.is_active:
                            return Response(
                                {"error": "This hotel account is suspended. Please contact platform support."},
                                status=status.HTTP_403_FORBIDDEN,
                            )
                        
                        if (
                            current_schema != "public"
                            and user.tenant_schema
                            and user.tenant_schema != current_schema
                        ):
                            return Response(
                                {"error": "Your account does not have access to this hotel."},
                                status=status.HTTP_403_FORBIDDEN,
                            )
                    except Exception:
                        pass

                tokens = get_tokens_for_user(user)
                return Response(
                    {"message": "Login Successful", "tokens": tokens, "user": UserSerializer(user).data},
                    status=status.HTTP_200_OK,
                )
            return Response({"error": "Invalid password!"}, status=status.HTTP_401_UNAUTHORIZED)
        except User.DoesNotExist:
            return Response({"error": "No account found with this email!"}, status=status.HTTP_401_UNAUTHORIZED)


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            is_admin_creating = request.user.is_authenticated and request.user.role == "admin"
            user = serializer.save()
            user.set_password(request.data.get("password"))
            user.role = request.data.get("role", "waiter")

            # Assign new staff to the current tenant schema
            try:
                from django.db import connection
                if connection.schema_name != "public":
                    user.tenant_schema = connection.schema_name
            except Exception:
                pass

            if is_admin_creating:
                user.is_active = True
                user.save()
                return Response(
                    {"message": "User created successfully by Admin!", "user": UserSerializer(user).data},
                    status=status.HTTP_201_CREATED,
                )

            otp = str(random.randint(100000, 999999))
            user.otp_code = otp
            user.is_active = False
            user.save()

            try:
                send_mail(
                    "ACRMA TECH - Verification Code",
                    f"Welcome! Your verification code is: {otp}",
                    settings.EMAIL_HOST_USER,
                    [user.email],
                )
            except Exception as exc:
                print(f"Email error: {exc}")

            return Response(
                {"message": "Registration successful! Check email.", "user": UserSerializer(user).data},
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VerifyOTPView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get("email")
        otp = request.data.get("otp")
        try:
            user = User.objects.get(email=email, otp_code=otp)
            user.is_active = True
            user.otp_code = None
            user.save()
            return Response({"message": "Account activated successfully!"}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({"error": "Invalid OTP code or email."}, status=status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────────────────────────────────────
# ViewSets
# ─────────────────────────────────────────────────────────────────────────────

class UserViewSet(viewsets.ModelViewSet):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        from django.db import connection
        current_schema = connection.schema_name
        
        # Isolation: Only show users belonging to the current hotel's schema
        if current_schema != 'public':
            return User.objects.filter(tenant_schema=current_schema).order_by("-id")
            
        return User.objects.all().order_by("-id")

    def perform_create(self, serializer):
        from django.db import connection
        current_schema = connection.schema_name
        
        is_active_val = self.request.data.get("is_active", True)
        if isinstance(is_active_val, str):
            is_active_val = is_active_val.lower() == "true"
            
        # Set tenant_schema automatically based on the current subdomain/schema
        serializer.save(
            is_active=is_active_val,
            tenant_schema=current_schema if current_schema != 'public' else ''
        )


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class MenuItemViewSet(viewsets.ModelViewSet):
    queryset = MenuItem.objects.all()
    serializer_class = MenuItemSerializer


class RoomViewSet(viewsets.ModelViewSet):
    queryset = Room.objects.all()
    serializer_class = RoomSerializer


class ReserveRoomNowView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, room_id):
        try:
            room = Room.objects.get(id=room_id)
        except Room.DoesNotExist:
            return Response({"error": "Room not found."}, status=status.HTTP_404_NOT_FOUND)

        if room.status in ["Occupied", "Maintenance"]:
            return Response(
                {"error": f"Room {room.room_number} is currently {room.status.lower()}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        source = request.data.get("source") or "reception"
        if source == "public" and not room.is_available_online:
            return Response(
                {"error": "This room is not enabled for online booking."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        guest_name = request.data.get("guest_name") or "Guest"
        guest_email = request.data.get("guest_email") or ""
        guest_phone = request.data.get("guest_phone") or ""
        adults = int(request.data.get("adults") or 1)
        children = int(request.data.get("children") or 0)
        notes = request.data.get("notes") or ""

        try:
            check_in_date = datetime.fromisoformat(request.data.get("check_in_date")).date()
            check_out_date = datetime.fromisoformat(request.data.get("check_out_date")).date()
        except Exception:
            return Response({"error": "Check-in and check-out dates are required."}, status=status.HTTP_400_BAD_REQUEST)

        if check_out_date <= check_in_date:
            return Response({"error": "Check-out must be after check-in."}, status=status.HTTP_400_BAD_REQUEST)

        if reservation_overlaps(room, check_in_date, check_out_date):
            return Response({"error": "This room is already reserved for the selected dates."}, status=status.HTTP_400_BAD_REQUEST)

        _, total_amount, deposit_amount = calculate_reservation_amounts(room, check_in_date, check_out_date)

        reservation = Reservation.objects.create(
            room=room,
            guest_name=guest_name,
            guest_email=guest_email,
            guest_phone=guest_phone,
            check_in_date=check_in_date,
            check_out_date=check_out_date,
            adults=adults,
            children=children,
            notes=notes,
            source=source,
            total_amount=total_amount,
            deposit_amount=deposit_amount,
        )
        reservation.ensure_tokens()

        if source == "reception" and str(request.data.get("pay_now", "false")).lower() != "true":
            reservation.status = "confirmed"
            reservation.payment_status = "pending"
            reservation.save(update_fields=["confirmation_code", "qr_token", "public_token", "status", "payment_status", "updated_at"])
            room.status = "Reserved"
            room.booking_source = "front_desk"
            room.save(update_fields=["status", "booking_source"])
            summary = send_reservation_confirmation(reservation)
            return Response(
                {
                    "message": "Reception reservation created successfully.",
                    "reservation": summary,
                },
                status=status.HTTP_201_CREATED,
            )

        tx_ref = f"room-res-{reservation.id}-{uuid4().hex[:10]}"
        callback_url = f"{settings.BACKEND_BASE_URL.rstrip('/')}/api/users/payments/chapa/webhook/"
        return_url = f"{create_public_reservation_url(reservation, request=request)}?payment=returned"
        payload = {
            "amount": str(deposit_amount),
            "currency": "ETB",
            "email": guest_email or "guest@example.com",
            "first_name": guest_name,
            "last_name": room.name,
            "tx_ref": tx_ref,
            "callback_url": callback_url,
            "return_url": return_url,
            "customization": {
                "title": "Room Reservation Deposit",
                "description": f"Reservation for room {room.room_number} from {check_in_date.isoformat()} to {check_out_date.isoformat()}",
            },
            "meta": {
                "reservation_id": reservation.id,
                "room_id": room.id,
                "room_number": room.room_number,
                "check_in_date": check_in_date.isoformat(),
                "check_out_date": check_out_date.isoformat(),
                "booking_source": source,
            },
        }

        try:
            chapa_response = chapa_request("transaction/initialize", payload=payload, method="POST")
            checkout_url = (
                chapa_response.get("data", {}).get("checkout_url")
                or chapa_response.get("data", {}).get("link")
                or chapa_response.get("checkout_url")
            )
            if not checkout_url:
                raise ValueError("Chapa did not return a checkout URL.")
        except ValueError as exc:
            reservation.payment_status = "failed"
            reservation.save(update_fields=["payment_status", "updated_at"])
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        reservation.chapa_tx_ref = tx_ref
        reservation.chapa_checkout_url = checkout_url
        reservation.save(update_fields=["confirmation_code", "qr_token", "public_token", "chapa_tx_ref", "chapa_checkout_url", "updated_at"])
        room.status = "Reserved"
        room.booking_source = "online" if source == "public" else "front_desk"
        room.save(update_fields=["status", "booking_source"])

        return Response(
            {
                "message": "Reservation created successfully.",
                "checkout_url": checkout_url,
                "amount": float(deposit_amount),
                "tx_ref": tx_ref,
                "reservation": build_reservation_summary(reservation),
            },
            status=status.HTTP_201_CREATED,
        )


class UpdateRoomFrontDeskStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, room_id):
        try:
            room = Room.objects.get(id=room_id)
        except Room.DoesNotExist:
            return Response({"error": "Room not found."}, status=status.HTTP_404_NOT_FOUND)

        action = request.data.get("action")
        reservation = None
        reservation_id = request.data.get("reservation_id")
        if reservation_id:
            reservation = Reservation.objects.filter(id=reservation_id, room=room).first()

        if action == "checkin":
            room.status = "Occupied"
            if reservation:
                reservation.status = "checked_in"
                reservation.checked_in_at = timezone.now()
                reservation.save(update_fields=["status", "checked_in_at", "updated_at"])
        elif action == "checkout":
            room.status = "Cleaning"
            if reservation:
                reservation.status = "checked_out"
                reservation.checked_out_at = timezone.now()
                reservation.save(update_fields=["status", "checked_out_at", "updated_at"])
        else:
            return Response({"error": "Invalid action."}, status=status.HTTP_400_BAD_REQUEST)

        room.booking_source = request.data.get("booking_source") or room.booking_source
        room.save(update_fields=["status", "booking_source"])
        return Response({"message": "Room status updated.", "status": room.status})


class PublicRoomCatalogView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        try:
            check_in_param = request.query_params.get("check_in_date")
            check_out_param = request.query_params.get("check_out_date")
            online_qs = Room.objects.filter(is_available_online=True).order_by("priority", "room_number")
            qs = online_qs if online_qs.exists() else Room.objects.all().order_by("priority", "room_number")
            
            print(f"DEBUG: Found {qs.count()} rooms total.")
            payload = []
            for room in qs:
                is_available = True
                if check_in_param and check_out_param:
                    try:
                        check_in_date = datetime.fromisoformat(check_in_param).date()
                        check_out_date = datetime.fromisoformat(check_out_param).date()
                        is_available = not reservation_overlaps(room, check_in_date, check_out_date)
                    except Exception as e:
                        print(f"DEBUG: Date error for room {room.id}: {e}")
                        is_available = True

                image_url = None
                if room.main_image:
                    try:
                        image_url = request.build_absolute_uri(room.main_image.url)
                    except:
                        image_url = room.main_image.name # fallback
                        
                image_2_url = None
                if room.image_2:
                    try:
                        image_2_url = request.build_absolute_uri(room.image_2.url)
                    except:
                        image_2_url = room.image_2.name # fallback
                        
                image_3_url = None
                if room.image_3:
                    try:
                        image_3_url = request.build_absolute_uri(room.image_3.url)
                    except:
                        image_3_url = room.image_3.name # fallback
                
                payload.append({
                    "id": room.id,
                    "name": room.name,
                    "room_number": room.room_number,
                    "room_type": room.room_type,
                    "description": room.description,
                    "base_price": float(room.base_price or 0.0),
                    "weekend_price": float(room.weekend_price or room.base_price or 0.0),
                    "main_image": image_url,
                    "image_2": image_2_url,
                    "image_3": image_3_url,
                    "amenities": room.amenities or [],
                    "common_amenities": room.common_amenities or [],
                    "max_adults": room.max_adults,
                    "max_children": room.max_children,
                    "check_in_time": str(room.check_in_time),
                    "check_out_time": str(room.check_out_time),
                    "min_stay": room.min_stay,
                    "is_available": is_available and room.status not in ["Occupied", "Maintenance"],
                    "is_online_enabled": bool(room.is_available_online),
                    "deposit_type": room.online_deposit_type,
                    "deposit_amount": float(room.advance_payment_amount or 0),
                })
            print(f"DEBUG: Returning {len(payload)} items.")
            return Response(payload)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({"error": f"Internal Server Error: {str(e)}"}, status=500)


class ReservationListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        reservations = Reservation.objects.select_related("room").all()[:100]
        return Response(ReservationSerializer(reservations, many=True).data)


class CurrentTenantPublicSiteView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        from tenants.models import Domain

        schema_name = connection.schema_name
        domain_obj = None
        if schema_name and schema_name != "public":
            domain_obj = Domain.objects.filter(tenant__schema_name=schema_name, is_primary=True).select_related("tenant").first()

        return Response(
            {
                "schema_name": schema_name,
                "domain": domain_obj.domain if domain_obj else "",
                "public_site_url": f"{get_tenant_frontend_base(request=request)}/customer-dashboard",
            }
        )


class PublicRoomReserveView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, room_id):
        try:
            online_rooms_exist = Room.objects.filter(is_available_online=True).exists()
            try:
                if online_rooms_exist:
                    room = Room.objects.get(id=room_id, is_available_online=True)
                else:
                    room = Room.objects.get(id=room_id)
            except Room.DoesNotExist:
                return Response({"error": "Room not found or not available online."}, status=404)

            try:
                check_in_date = datetime.fromisoformat(request.data.get("check_in_date")).date()
                check_out_date = datetime.fromisoformat(request.data.get("check_out_date")).date()
            except Exception:
                return Response({"error": "Valid check-in and check-out dates are required."}, status=400)

            if check_out_date <= check_in_date:
                return Response({"error": "Check-out must be after check-in."}, status=400)
            if reservation_overlaps(room, check_in_date, check_out_date):
                return Response({"error": "This room is already reserved for the selected dates."}, status=400)

            guest_name = request.data.get("guest_name") or "Guest"
            guest_email = request.data.get("guest_email") or ""
            guest_phone = request.data.get("guest_phone") or ""
            adults = int(request.data.get("adults") or 1)
            children = int(request.data.get("children") or 0)
            notes = request.data.get("notes") or ""
            _, total_amount, deposit_amount = calculate_reservation_amounts(room, check_in_date, check_out_date)

            reservation = Reservation.objects.create(
                room=room,
                guest_name=guest_name,
                guest_email=guest_email,
                guest_phone=guest_phone,
                check_in_date=check_in_date,
                check_out_date=check_out_date,
                adults=adults,
                children=children,
                notes=notes,
                source="public",
                total_amount=total_amount,
                deposit_amount=deposit_amount,
            )
            reservation.ensure_tokens()

            tx_ref = f"room-res-{reservation.id}-{uuid4().hex[:10]}"
            callback_url = f"{settings.BACKEND_BASE_URL.rstrip('/')}/api/users/payments/chapa/webhook/"
            return_url = f"{create_public_reservation_url(reservation, request=request)}?payment=returned"
            payload = {
                "amount": str(deposit_amount),
                "currency": "ETB",
                "email": guest_email or "guest@example.com",
                "first_name": guest_name,
                "last_name": room.name,
                "tx_ref": tx_ref,
                "callback_url": callback_url,
                "return_url": return_url,
                "customization": {
                    "title": "Room Deposit",
                    "description": f"Room {room.room_number} from {check_in_date.isoformat()} to {check_out_date.isoformat()}",
                },
                "meta": {
                    "reservation_id": reservation.id,
                    "room_id": room.id,
                    "room_number": room.room_number,
                    "check_in_date": check_in_date.isoformat(),
                    "check_out_date": check_out_date.isoformat(),
                    "booking_source": "public",
                },
            }

            try:
                chapa_response = chapa_request("transaction/initialize", payload=payload, method="POST")
                checkout_url = (
                    chapa_response.get("data", {}).get("checkout_url")
                    or chapa_response.get("data", {}).get("link")
                    or chapa_response.get("checkout_url")
                )
                if not checkout_url:
                    raise ValueError("Chapa did not return a checkout URL.")
            except ValueError as exc:
                reservation.payment_status = "failed"
                reservation.save(update_fields=["payment_status", "updated_at"])
                return Response({"error": str(exc)}, status=400)

            reservation.chapa_tx_ref = tx_ref
            reservation.chapa_checkout_url = checkout_url
            reservation.save(update_fields=["confirmation_code", "qr_token", "public_token", "chapa_tx_ref", "chapa_checkout_url", "updated_at"])
            room.status = "Reserved"
            room.booking_source = "online"
            room.save(update_fields=["status", "booking_source"])

            return Response(
                {
                    "message": "Public reservation created successfully.",
                    "checkout_url": checkout_url,
                    "reservation": build_reservation_summary(reservation),
                },
                status=201,
            )
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({"error": f"Internal Server Error: {str(e)}"}, status=500)


class PublicReservationDetailView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, token):
        try:
            reservation = get_public_reservation_from_token(token)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=404)
        return Response(build_reservation_summary(reservation))


class PublicReservationVerifyPaymentView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, token):
        try:
            reservation = get_public_reservation_from_token(token)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=404)

        if reservation.payment_status == "paid":
            return Response({"message": "Payment already verified.", "reservation": send_reservation_confirmation(reservation)})

        tx_ref = request.data.get("tx_ref") or reservation.chapa_tx_ref
        if not tx_ref:
            return Response({"error": "No pending Chapa transaction found for this reservation."}, status=400)

        try:
            verification = verify_chapa_transaction(tx_ref)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=400)

        verification_data = verification.get("data", verification)
        status_value = str(verification_data.get("status", "")).lower()
        if status_value not in {"success", "successful"}:
            return Response({"message": "Payment is still pending.", "status": status_value or "pending"}, status=202)

        summary = finalize_paid_reservation(reservation, payment_reference=tx_ref)
        return Response({"message": "Reservation payment verified successfully.", "reservation": summary})


class PublicQRCheckInView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        qr_token = request.data.get("qr_token")
        if not qr_token:
            return Response({"error": "QR token is required."}, status=400)
        reservation = Reservation.objects.select_related("room").filter(
            models.Q(qr_token=qr_token) | models.Q(confirmation_code=qr_token)
        ).first()
        if not reservation:
            return Response({"error": "Reservation not found with this code or QR."}, status=404)

        reservation.status = "checked_in"
        reservation.checked_in_at = timezone.now()
        reservation.save(update_fields=["status", "checked_in_at", "updated_at"])
        reservation.room.status = "Occupied"
        reservation.room.booking_source = "front_desk"
        reservation.room.save(update_fields=["status", "booking_source"])
        return Response({"message": "Guest checked in successfully.", "reservation": build_reservation_summary(reservation)})


class RestaurantTableViewSet(viewsets.ModelViewSet):
    serializer_class = RestaurantTableSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return RestaurantTable.objects.all().order_by("table_code")


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard & Orders
# ─────────────────────────────────────────────────────────────────────────────

class DashboardStatsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        paid_orders = Order.objects.filter(payment_status="paid")
        data = {
            "metrics": {
                "totalOrders": Order.objects.count(),
                "revenue": float(sum(o.total_amount for o in paid_orders)),
                "tips": float(sum(o.tip_amount for o in paid_orders)),
                "pendingOrders": Order.objects.filter(status="pending").count(),
                "totalRooms": Room.objects.count(),
            },
            "chartPoints": [1200, 1900, 3000, 5000, 2000, 4000],
        }
        return Response(data)


class CreateOrderView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        data = request.data
        try:
            with transaction.atomic():
                table = RestaurantTable.objects.get(id=data.get("table_id"))
                order = Order.objects.create(
                    table=table,
                    waiter_id_ref=request.user.id,
                    waiter_username=request.user.username,
                    status="pending",
                    payment_status="pending",
                )

                table.status = "occupied"
                table.save(update_fields=["status"])

                for item in data.get("items", []):
                    menu_item = MenuItem.objects.get(id=item["id"])
                    OrderItem.objects.create(
                        order=order,
                        menu_item=menu_item,
                        quantity=item["quantity"],
                        price_at_order=menu_item.price,
                    )

                sync_order_financials(order)
                return Response(
                    {"message": "Order sent to kitchen!", "order_id": order.id},
                    status=status.HTTP_201_CREATED,
                )
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class KitchenOrdersView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        orders = Order.objects.filter(status__in=["pending", "preparing"]).order_by("created_at")
        return Response(OrderSerializer(orders, many=True).data)


class UpdateOrderStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, order_id):
        try:
            order = Order.objects.get(id=order_id)
            new_status = request.data.get("status")
            order.status = new_status
            order.save(update_fields=["status", "updated_at"])

            if new_status == "ready" and order.waiter_id_ref:
                Notification.objects.create(
                    user_id_ref=order.waiter_id_ref,
                    message=(
                        f"Order #ORD-{order.id} (Table {order.table.table_code}) "
                        f"is ready. Please serve the customer."
                    ),
                )

            return Response({"message": f"Order status updated to {new_status}"})
        except Order.DoesNotExist:
            return Response({"error": "Order not found"}, status=404)


class WaiterOrdersView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        limit = request.query_params.get("limit")

        base_qs = (
            Order.objects.filter(waiter_id_ref=request.user.id)
            .prefetch_related("items__menu_item")
            .select_related("table")
        )
        active_qs = base_qs.exclude(payment_status="paid").order_by("-updated_at")
        completed_qs = base_qs.filter(payment_status="paid").order_by("-updated_at")

        if start_date:
            completed_qs = completed_qs.filter(updated_at__date__gte=start_date)
        if end_date:
            completed_qs = completed_qs.filter(updated_at__date__lte=end_date)
        if limit:
            try:
                completed_qs = completed_qs[: int(limit)]
            except ValueError:
                pass

        active_orders = sorted(
            list(active_qs),
            key=lambda o: (_WAITER_STATUS_PRIORITY.get(o.status, 9), -o.updated_at.timestamp()),
        )
        completed_orders = list(completed_qs)
        orders = active_orders + completed_orders
        for order in orders:
            sync_order_financials(order, save=False)
        return Response(OrderSerializer(orders, many=True).data)


class MarkOrderServedView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, order_id):
        try:
            order = Order.objects.get(id=order_id, waiter_id_ref=request.user.id)
            order.status = "served"
            order.save(update_fields=["status", "updated_at"])
            return Response({"message": "Order marked as served!"})
        except Order.DoesNotExist:
            return Response({"error": "Order not found"}, status=404)


class RequestBillView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, order_id):
        try:
            order = Order.objects.get(id=order_id, waiter_id_ref=request.user.id)
            sync_order_financials(order)
            order.status = "bill_requested"
            order.save(
                update_fields=["status", "sub_total", "service_charge_amount", "vat_amount", "total_amount", "updated_at"]
            )
            message = f"Bill requested for Table {order.table.table_code}. Please process payment."
            cashiers = User.objects.filter(role="cashier", is_active=True)
            if cashiers.exists():
                notify_users(cashiers, message)
            else:
                Notification.objects.create(user_id_ref=request.user.id, message=message)
            return Response({"message": "Bill request sent successfully!"})
        except Order.DoesNotExist:
            return Response({"error": "Order not found"}, status=404)


class CompleteOrderView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, order_id):
        try:
            with transaction.atomic():
                order = Order.objects.get(id=order_id)
                finalize_paid_order(
                    order,
                    payment_method=request.data.get("payment_method", "Cash"),
                    payment_reference=request.data.get("payment_reference", f"CASH-{order.id}"),
                    tip_amount=request.data.get("tip_amount", order.tip_amount),
                    cashier=request.user if request.user.role == "cashier" else None,
                )
                return Response({"message": "Payment completed. Table is now available!"})
        except Order.DoesNotExist:
            return Response({"error": "Order not found"}, status=404)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────────────────────────────────────
# Notifications
# ─────────────────────────────────────────────────────────────────────────────

class NotificationView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        notifs = Notification.objects.filter(user_id_ref=request.user.id).order_by("-created_at")
        return Response(NotificationSerializer(notifs, many=True).data)

    def delete(self, request):
        Notification.objects.filter(user_id_ref=request.user.id).delete()
        return Response({"message": "All notifications deleted"}, status=status.HTTP_204_NO_CONTENT)


class NotificationDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, pk):
        try:
            notif = Notification.objects.get(pk=pk, user_id_ref=request.user.id)
            notif.delete()
            return Response({"message": "Notification deleted"})
        except Notification.DoesNotExist:
            return Response(status=404)


# ─────────────────────────────────────────────────────────────────────────────
# System Settings
# ─────────────────────────────────────────────────────────────────────────────

class SystemSettingsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(SystemSettingsSerializer(get_system_settings()).data)

    def post(self, request):
        if request.user.role != "admin":
            return Response({"error": "Only admins can modify system settings."}, status=403)
        settings_obj = get_system_settings()
        serializer = SystemSettingsSerializer(settings_obj, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)


# ─────────────────────────────────────────────────────────────────────────────
# Payment & Checkout
# ─────────────────────────────────────────────────────────────────────────────

class OrderPaymentSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, order_id):
        try:
            order = (
                Order.objects.prefetch_related("items__menu_item")
                .select_related("table")
                .get(id=order_id)
            )
        except Order.DoesNotExist:
            return Response({"error": "Order not found"}, status=404)

        if request.user.role == "waiter" and order.waiter_id_ref != request.user.id:
            return Response({"error": "You can only access your own orders."}, status=403)

        return Response(build_payment_summary(order))


class WaiterCashPaymentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, order_id):
        try:
            order = (
                Order.objects.select_related("table")
                .prefetch_related("items__menu_item")
                .get(id=order_id, waiter_id_ref=request.user.id)
            )
        except Order.DoesNotExist:
            return Response({"error": "Order not found"}, status=404)

        if order.payment_status == "paid":
            return Response({"error": "Order is already paid."}, status=400)

        with transaction.atomic():
            finalize_paid_order(
                order,
                payment_method="Cash",
                payment_reference=request.data.get(
                    "payment_reference",
                    f"CASH-{order.id}-{timezone.now().strftime('%H%M%S')}",
                ),
                tip_amount=request.data.get("tip_amount", 0),
            )
        return Response({"message": "Cash payment recorded successfully.", "summary": build_payment_summary(order)})


class CreateDigitalPaymentSessionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, order_id):
        try:
            order = (
                Order.objects.select_related("table")
                .prefetch_related("items__menu_item")
                .get(id=order_id, waiter_id_ref=request.user.id)
            )
        except Order.DoesNotExist:
            return Response({"error": "Order not found"}, status=404)

        order.ensure_payment_page_token()
        order.payment_method = "Chapa"
        order.payment_status = "pending"
        order.save(update_fields=["payment_page_token", "payment_method", "payment_status", "updated_at"])

        return Response(
            {
                "message": "Digital payment session created.",
                "payment_page_url": create_payment_page_url(order),
                "token": order.payment_page_token,
                "summary": build_payment_summary(order),
            }
        )


# ─────────────────────────────────────────────────────────────────────────────
# Cashier Views
# ─────────────────────────────────────────────────────────────────────────────

class CashierOrderProcessView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, order_id):
        try:
            order = Order.objects.prefetch_related("items__menu_item").select_related("table").get(id=order_id)
        except Order.DoesNotExist:
            return Response({"error": "Order not found"}, status=404)

        with transaction.atomic():
            finalize_paid_order(
                order,
                payment_method=request.data.get("payment_method", "Cash"),
                payment_reference=request.data.get(
                    "payment_reference", f"POS-{order.id}-{timezone.now().strftime('%H%M%S')}"
                ),
                tip_amount=request.data.get("tip_amount", order.tip_amount),
                cashier=request.user,
            )

        summary = build_payment_summary(order)
        return Response({"message": "Payment processed successfully!", "receipt_data": summary})


class CashierPendingBillsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        orders = (
            Order.objects.filter(
                status__in=["bill_requested", "served"],
                payment_status="pending",
            ).order_by("-updated_at")
        )
        return Response(OrderSerializer(orders, many=True).data)


class CashierCompletedBillsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        limit = request.query_params.get("limit")

        orders = Order.objects.filter(payment_status="paid").order_by("-updated_at")
        if start_date:
            orders = orders.filter(updated_at__date__gte=start_date)
        if end_date:
            orders = orders.filter(updated_at__date__lte=end_date)
        if limit:
            try:
                orders = orders[: int(limit)]
            except ValueError:
                pass
        return Response(OrderSerializer(orders, many=True).data)


class CashierReceiptView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, order_id):
        try:
            order = Order.objects.prefetch_related("items__menu_item").select_related("table").get(id=order_id)
        except Order.DoesNotExist:
            return Response({"error": "Order not found"}, status=404)

        if order.payment_status != "paid":
            return Response({"error": "Order is not finalized for receipt printing"}, status=400)

        settings_obj = get_system_settings()
        items_data = [
            {
                "menu_item_name": item.menu_item.name,
                "quantity": item.quantity,
                "price_at_order": float(item.price_at_order),
            }
            for item in order.items.all()
        ]

        return Response(
            {
                "order_id": order.id,
                "table_code": order.table.table_code if order.table else "",
                "items": items_data,
                "sub_total": float(order.sub_total),
                "service_charge": float(order.service_charge_amount),
                "vat": float(order.vat_amount),
                "grand_total": float(order.total_amount),
                "tip_amount": float(order.tip_amount),
                "payment_method": order.payment_method or "Cash",
                "payment_reference": order.payment_reference or "",
                "processed_at": order.updated_at.isoformat(),
                "fiscal_number": f"FS{order.id:06d}",
                "tin_number": settings_obj.tin_number,
                "address": settings_obj.address,
                "phone_number": settings_obj.phone_number,
                "fiscal_machine_no": settings_obj.fiscal_machine_no,
            }
        )


# ─────────────────────────────────────────────────────────────────────────────
# Public Payment Pages (no auth required — customer-facing)
# ─────────────────────────────────────────────────────────────────────────────

class PublicPaymentDetailView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, token):
        try:
            order = get_public_order_from_token(token)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=404)

        payload = build_payment_summary(order)
        payload["items"] = [
            {
                "menu_item_name": item.menu_item.name,
                "quantity": item.quantity,
                "price_at_order": float(item.price_at_order),
            }
            for item in order.items.all()
        ]
        # waiter_username is a denormalized field — safe cross-schema
        payload["waiter_name"] = order.waiter_username or "Waiter"
        return Response(payload)


class PublicVerifyChapaPaymentView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, token):
        try:
            order = get_public_order_from_token(token)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=404)

        if order.payment_status == "paid":
            return Response({"message": "Payment already verified.", "summary": build_payment_summary(order)})

        tx_ref = request.data.get("tx_ref") or order.chapa_tx_ref
        if not tx_ref:
            return Response({"error": "No pending Chapa transaction found for this order."}, status=400)

        try:
            verification = verify_chapa_transaction(tx_ref)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=400)

        verification_data = verification.get("data", verification)
        status_value = str(verification_data.get("status", "")).lower()
        if status_value not in {"success", "successful"}:
            return Response({"message": "Payment is still pending.", "status": status_value or "pending"}, status=202)

        amount = to_decimal(verification_data.get("amount", order.total_amount))
        base_total = to_decimal(order.total_amount)
        tip_amount = order.tip_amount
        if amount > base_total:
            tip_amount = (amount - base_total).quantize(TWOPLACES, rounding=ROUND_HALF_UP)

        with transaction.atomic():
            finalize_paid_order(order, payment_method="Chapa", payment_reference=tx_ref, tip_amount=tip_amount)

        if order.waiter_id_ref:
            Notification.objects.create(
                user_id_ref=order.waiter_id_ref,
                message=f"Digital payment completed for Table {order.table.table_code}.",
            )

        return Response({"message": "Payment verified successfully.", "summary": build_payment_summary(order)})


class PublicInitiateChapaPaymentView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, token):
        try:
            order = get_public_order_from_token(token)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=404)

        if order.payment_status == "paid":
            return Response({"error": "Order is already paid."}, status=400)

        tip_amount = to_decimal(request.data.get("tip_amount", 0))
        if tip_amount < Decimal("0.00"):
            return Response({"error": "Tip cannot be negative."}, status=400)

        summary = build_payment_summary(order)
        amount_due = to_decimal(summary["grand_total"]) + tip_amount
        tx_ref = generate_tx_ref(order)
        return_url = f"{create_payment_page_url(order, request=request)}?payment=returned"
        callback_url = f"{settings.BACKEND_BASE_URL.rstrip('/')}{reverse('chapa-webhook')}"
        customer_email = request.data.get("email") or f"guest-order-{order.id}@example.com"
        first_name = request.data.get("first_name") or "Guest"
        last_name = request.data.get("last_name") or f"Order{order.id}"

        payload = {
            "amount": str(amount_due),
            "currency": "ETB",
            "email": customer_email,
            "first_name": first_name,
            "last_name": last_name,
            "tx_ref": tx_ref,
            "callback_url": callback_url,
            "return_url": return_url,
            "customization": {
                "title": f"Order {order.id}",
                "description": f"Table {order.table.table_code} checkout",
            },
            "meta": {
                "order_id": order.id,
                "base_total": str(order.total_amount),
                "tip_amount": str(tip_amount),
            },
        }

        try:
            chapa_response = chapa_request("transaction/initialize", payload=payload, method="POST")
        except ValueError as exc:
            return Response({"error": str(exc)}, status=400)

        checkout_url = (
            chapa_response.get("data", {}).get("checkout_url")
            or chapa_response.get("data", {}).get("link")
            or chapa_response.get("checkout_url")
        )
        if not checkout_url:
            return Response({"error": "Chapa did not return a checkout URL."}, status=400)

        order.tip_amount = tip_amount
        order.payment_method = "Chapa"
        order.payment_reference = tx_ref
        order.chapa_tx_ref = tx_ref
        order.chapa_checkout_url = checkout_url
        order.payment_status = "pending"
        order.save(
            update_fields=[
                "tip_amount", "payment_method", "payment_reference",
                "chapa_tx_ref", "chapa_checkout_url", "payment_status", "updated_at",
            ]
        )

        return Response(
            {
                "checkout_url": checkout_url,
                "tx_ref": tx_ref,
                "amount_due": float(amount_due),
                "tip_amount": float(tip_amount),
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class ChapaWebhookView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        if not is_valid_chapa_signature(request):
            return Response({"error": "Invalid Chapa signature"}, status=403)

        payload = request.data or {}
        tx_ref = (
            payload.get("tx_ref")
            or payload.get("trx_ref")
            or payload.get("data", {}).get("tx_ref")
            or payload.get("data", {}).get("trx_ref")
        )
        if not tx_ref:
            return Response({"error": "Missing tx_ref"}, status=400)

        try:
            verification = verify_chapa_transaction(tx_ref)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=400)

        verification_data = verification.get("data", verification)
        status_value = str(verification_data.get("status", "")).lower()
        if status_value not in {"success", "successful"}:
            return Response({"message": "Payment not successful"}, status=202)

        reservation = Reservation.objects.select_related("room").filter(chapa_tx_ref=tx_ref).first()
        if reservation:
            summary = finalize_paid_reservation(reservation, payment_reference=tx_ref)
            return Response({"message": "Reservation webhook processed successfully", "reservation": summary})

        try:
            order = Order.objects.select_related("table").get(chapa_tx_ref=tx_ref)
        except Order.DoesNotExist:
            return Response({"error": "Payment record not found for tx_ref"}, status=404)

        amount = to_decimal(verification_data.get("amount", order.total_amount))
        base_total = to_decimal(order.total_amount)
        tip_amount = order.tip_amount
        if amount > base_total:
            tip_amount = (amount - base_total).quantize(TWOPLACES, rounding=ROUND_HALF_UP)

        with transaction.atomic():
            finalize_paid_order(order, payment_method="Chapa", payment_reference=tx_ref, tip_amount=tip_amount)

        if order.waiter_id_ref:
            Notification.objects.create(
                user_id_ref=order.waiter_id_ref,
                message=f"Digital payment completed for Table {order.table.table_code}.",
            )

        return Response({"message": "Webhook processed successfully"})


# =============================================================================
# PMS VIEWS — Property Management System
# =============================================================================

# ── Maintenance Log ───────────────────────────────────────────────────────────

class MaintenanceLogView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, room_id):
        try:
            room = Room.objects.get(id=room_id)
        except Room.DoesNotExist:
            return Response({"error": "Room not found."}, status=404)
        logs = MaintenanceLog.objects.filter(room=room)
        return Response(MaintenanceLogSerializer(logs, many=True).data)

    def post(self, request, room_id):
        try:
            room = Room.objects.get(id=room_id)
        except Room.DoesNotExist:
            return Response({"error": "Room not found."}, status=404)
        data = request.data.copy()
        data["room"] = room.id
        data.setdefault("reported_by", request.user.username)
        serializer = MaintenanceLogSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class MaintenanceLogDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, log_id):
        try:
            log = MaintenanceLog.objects.get(id=log_id)
        except MaintenanceLog.DoesNotExist:
            return Response({"error": "Log not found."}, status=404)
        serializer = MaintenanceLogSerializer(log, data=request.data, partial=True)
        if serializer.is_valid():
            if request.data.get("status") == "resolved" and not log.resolved_at:
                log.resolved_at = timezone.now()
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)


# ── Room History ──────────────────────────────────────────────────────────────

class RoomHistoryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, room_id):
        try:
            room = Room.objects.get(id=room_id)
        except Room.DoesNotExist:
            return Response({"error": "Room not found."}, status=404)
        history = RoomHistory.objects.filter(room=room)
        return Response(RoomHistorySerializer(history, many=True).data)


# ── Guest Profile ─────────────────────────────────────────────────────────────

class GuestProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        phone = request.query_params.get("phone")
        reservation_id = request.query_params.get("reservation_id")
        qs = GuestProfile.objects.all()
        if phone:
            qs = qs.filter(phone__icontains=phone)
        if reservation_id:
            qs = qs.filter(reservation_id=reservation_id)
        return Response(GuestProfileSerializer(qs[:50], many=True).data)

    def post(self, request):
        serializer = GuestProfileSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class GuestProfileDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        try:
            profile = GuestProfile.objects.get(pk=pk)
        except GuestProfile.DoesNotExist:
            return Response({"error": "Profile not found."}, status=404)
        return Response(GuestProfileSerializer(profile).data)

    def patch(self, request, pk):
        try:
            profile = GuestProfile.objects.get(pk=pk)
        except GuestProfile.DoesNotExist:
            return Response({"error": "Profile not found."}, status=404)
        serializer = GuestProfileSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)


# ── Folio Charges ─────────────────────────────────────────────────────────────

class FolioChargeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, reservation_id):
        charges = FolioCharge.objects.filter(reservation_id=reservation_id)
        return Response(FolioChargeSerializer(charges, many=True).data)

    def post(self, request, reservation_id):
        try:
            reservation = Reservation.objects.get(id=reservation_id)
        except Reservation.DoesNotExist:
            return Response({"error": "Reservation not found."}, status=404)
        data = request.data.copy()
        data["reservation"] = reservation.id
        data.setdefault("added_by", request.user.username)
        serializer = FolioChargeSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class FolioChargeDeleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, charge_id):
        try:
            charge = FolioCharge.objects.get(id=charge_id)
            charge.delete()
            return Response({"message": "Charge deleted."})
        except FolioCharge.DoesNotExist:
            return Response({"error": "Charge not found."}, status=404)


# ── Final Bill (Check-Out) ────────────────────────────────────────────────────

class GenerateFinalBillView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, reservation_id):
        try:
            reservation = Reservation.objects.select_related("room").get(id=reservation_id)
        except Reservation.DoesNotExist:
            return Response({"error": "Reservation not found."}, status=404)

        folio_charges = FolioCharge.objects.filter(reservation=reservation)
        nights = max((reservation.check_out_date - reservation.check_in_date).days, 1)
        room_total = to_decimal(reservation.room.base_price) * nights
        extras_total = sum(to_decimal(c.amount) for c in folio_charges)
        grand_total = room_total + extras_total

        settings_obj = get_system_settings()
        return Response({
            "reservation_id": reservation.id,
            "confirmation_code": reservation.confirmation_code,
            "guest_name": reservation.guest_name,
            "guest_phone": reservation.guest_phone,
            "room_name": reservation.room.name,
            "room_number": reservation.room.room_number,
            "check_in_date": reservation.check_in_date.isoformat(),
            "check_out_date": reservation.check_out_date.isoformat(),
            "nights": nights,
            "room_rate": float(reservation.room.base_price),
            "room_total": float(room_total),
            "folio_charges": FolioChargeSerializer(folio_charges, many=True).data,
            "extras_total": float(extras_total),
            "grand_total": float(grand_total),
            "hotel_name": settings_obj.hotel_name,
            "hotel_address": settings_obj.address,
            "hotel_phone": settings_obj.phone_number,
            "tin_number": settings_obj.tin_number,
            "printer_paper_size": settings_obj.printer_paper_size,
        })


# ── Digital Check-In (with Guest Registration) ────────────────────────────────

class DigitalCheckInView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, room_id):
        try:
            room = Room.objects.get(id=room_id)
        except Room.DoesNotExist:
            return Response({"error": "Room not found."}, status=404)

        if room.status == "Maintenance":
            return Response({"error": "Room is under maintenance (Out of Order)."}, status=400)

        # Find the active reservation for this room
        reservation = Reservation.objects.filter(
            room=room, status__in=["confirmed", "pending"]
        ).order_by("-created_at").first()

        with transaction.atomic():
            # Save guest profile if provided
            guest_data = request.data.get("guest_profile", {})
            if guest_data and reservation:
                profile_data = {
                    "reservation": reservation.id,
                    "full_name": guest_data.get("full_name", reservation.guest_name),
                    "phone": guest_data.get("phone", reservation.guest_phone or ""),
                    "nationality": guest_data.get("nationality", ""),
                    "id_type": guest_data.get("id_type", "national_id"),
                    "id_number": guest_data.get("id_number", ""),
                }
                existing = GuestProfile.objects.filter(reservation=reservation).first()
                if existing:
                    GuestProfileSerializer(existing, data=profile_data, partial=True).save() if GuestProfileSerializer(existing, data=profile_data, partial=True).is_valid() else None
                else:
                    s = GuestProfileSerializer(data=profile_data)
                    if s.is_valid():
                        s.save()

            # Update room and reservation
            room.status = "Occupied"
            room.save(update_fields=["status"])

            if reservation:
                reservation.status = "checked_in"
                reservation.checked_in_at = timezone.now()
                reservation.save(update_fields=["status", "checked_in_at", "updated_at"])

                # Log room history
                RoomHistory.objects.create(
                    room=room,
                    event_type="checkin",
                    guest_name=reservation.guest_name,
                    check_in_date=reservation.check_in_date,
                    check_out_date=reservation.check_out_date,
                    notes=f"Check-in by {request.user.username}",
                )

        return Response({
            "message": "Guest checked in successfully.",
            "room_status": room.status,
            "reservation_id": reservation.id if reservation else None,
        })


# ── Enhanced Checkout (auto Final Bill + RoomHistory) ────────────────────────

class EnhancedCheckoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, reservation_id):
        try:
            reservation = Reservation.objects.select_related("room").get(id=reservation_id)
        except Reservation.DoesNotExist:
            return Response({"error": "Reservation not found."}, status=404)

        room = reservation.room
        nights = max((reservation.check_out_date - reservation.check_in_date).days, 1)
        room_total = to_decimal(room.base_price) * nights
        folio_charges = FolioCharge.objects.filter(reservation=reservation)
        extras_total = sum(to_decimal(c.amount) for c in folio_charges)
        grand_total = room_total + extras_total

        with transaction.atomic():
            reservation.status = "checked_out"
            reservation.checked_out_at = timezone.now()
            reservation.save(update_fields=["status", "checked_out_at", "updated_at"])

            room.status = "Cleaning"
            room.booking_source = "front_desk"
            room.save(update_fields=["status", "booking_source"])

            RoomHistory.objects.create(
                room=room,
                event_type="checkout",
                guest_name=reservation.guest_name,
                check_in_date=reservation.check_in_date,
                check_out_date=reservation.check_out_date,
                revenue=grand_total,
                notes=f"Checkout by {request.user.username}",
            )

        settings_obj = get_system_settings()
        return Response({
            "message": "Guest checked out. Room set to Cleaning.",
            "final_bill": {
                "reservation_id": reservation.id,
                "confirmation_code": reservation.confirmation_code,
                "guest_name": reservation.guest_name,
                "guest_phone": reservation.guest_phone,
                "room_name": room.name,
                "room_number": room.room_number,
                "check_in_date": reservation.check_in_date.isoformat(),
                "check_out_date": reservation.check_out_date.isoformat(),
                "nights": nights,
                "room_rate": float(room.base_price),
                "room_total": float(room_total),
                "folio_charges": FolioChargeSerializer(folio_charges, many=True).data,
                "extras_total": float(extras_total),
                "grand_total": float(grand_total),
                "hotel_name": settings_obj.hotel_name,
                "hotel_address": settings_obj.address,
                "hotel_phone": settings_obj.phone_number,
                "tin_number": settings_obj.tin_number,
            },
        })


# =============================================================================
# REPORTING VIEWS
# =============================================================================

class PoliceReportView(APIView):
    """Today's checked-in guests with ID information for police report."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if request.user.role not in ["admin", "reception"]:
            return Response({"error": "Access denied."}, status=403)
        date_param = request.query_params.get("date", timezone.now().date().isoformat())
        try:
            report_date = datetime.fromisoformat(date_param).date()
        except Exception:
            report_date = timezone.now().date()

        reservations = Reservation.objects.filter(
            checked_in_at__date=report_date
        ).select_related("room").prefetch_related("guest_profile")

        rows = []
        for res in reservations:
            profile = getattr(res, "guest_profile", None)
            rows.append({
                "guest_name": res.guest_name,
                "room_number": res.room.room_number,
                "room_type": res.room.room_type,
                "check_in_date": res.check_in_date.isoformat(),
                "check_out_date": res.check_out_date.isoformat(),
                "nationality": profile.nationality if profile else "",
                "id_type": profile.id_type if profile else "",
                "id_number": profile.id_number if profile else "",
                "phone": res.guest_phone or (profile.phone if profile else ""),
            })
        return Response({"date": report_date.isoformat(), "guests": rows, "total": len(rows)})


class XReportView(APIView):
    """Live revenue snapshot for today (X-Report)."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if request.user.role not in ["admin", "reception"]:
            return Response({"error": "Access denied."}, status=403)
        date_param = request.query_params.get("date", timezone.now().date().isoformat())
        try:
            report_date = datetime.fromisoformat(date_param).date()
        except Exception:
            report_date = timezone.now().date()

        # Restaurant orders
        paid_orders = Order.objects.filter(payment_status="paid", updated_at__date=report_date)
        cash_total = sum(to_decimal(o.total_amount) for o in paid_orders if o.payment_method == "Cash")
        chapa_total = sum(to_decimal(o.total_amount) for o in paid_orders if o.payment_method == "Chapa")
        telebirr_total = sum(to_decimal(o.total_amount) for o in paid_orders if o.payment_method == "Telebirr")
        card_total = sum(to_decimal(o.total_amount) for o in paid_orders if o.payment_method == "Card")

        # Room revenue (checked out today)
        checked_out_today = RoomHistory.objects.filter(event_type="checkout", created_at__date=report_date)
        room_revenue = sum(to_decimal(r.revenue) for r in checked_out_today)

        restaurant_total = cash_total + chapa_total + telebirr_total + card_total
        grand_total = restaurant_total + room_revenue

        return Response({
            "report_type": "X-Report",
            "date": report_date.isoformat(),
            "restaurant": {
                "cash": float(cash_total),
                "chapa": float(chapa_total),
                "telebirr": float(telebirr_total),
                "card": float(card_total),
                "total": float(restaurant_total),
                "order_count": paid_orders.count(),
            },
            "rooms": {
                "revenue": float(room_revenue),
                "checkouts": checked_out_today.count(),
            },
            "grand_total": float(grand_total),
            "is_closed": False,
            "hotel_name": get_system_settings().hotel_name,
            "tin_number": get_system_settings().tin_number,
            "printer_paper_size": get_system_settings().printer_paper_size,
        })


class ZReportView(APIView):
    """End-of-day closure report (Z-Report) — snapshot, no locking."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if request.user.role not in ["admin", "reception"]:
            return Response({"error": "Access denied."}, status=403)
        date_param = request.data.get("date", timezone.now().date().isoformat())
        try:
            report_date = datetime.fromisoformat(date_param).date()
        except Exception:
            report_date = timezone.now().date()

        paid_orders = Order.objects.filter(payment_status="paid", updated_at__date=report_date)
        cash_total = sum(to_decimal(o.total_amount) for o in paid_orders if o.payment_method == "Cash")
        chapa_total = sum(to_decimal(o.total_amount) for o in paid_orders if o.payment_method == "Chapa")
        telebirr_total = sum(to_decimal(o.total_amount) for o in paid_orders if o.payment_method == "Telebirr")
        card_total = sum(to_decimal(o.total_amount) for o in paid_orders if o.payment_method == "Card")

        checked_out_today = RoomHistory.objects.filter(event_type="checkout", created_at__date=report_date)
        room_revenue = sum(to_decimal(r.revenue) for r in checked_out_today)
        restaurant_total = cash_total + chapa_total + telebirr_total + card_total
        grand_total = restaurant_total + room_revenue

        audit, _ = DayAuditLog.objects.get_or_create(audit_date=report_date)
        audit.is_closed = True
        audit.closed_at = timezone.now()
        audit.closed_by = request.user.username
        audit.total_cash = cash_total
        audit.total_chapa = chapa_total
        audit.total_telebirr = telebirr_total
        audit.total_card = card_total
        audit.total_room_revenue = room_revenue
        audit.total_revenue = grand_total
        audit.save()

        return Response({
            "report_type": "Z-Report",
            "date": report_date.isoformat(),
            "closed_by": request.user.username,
            "closed_at": audit.closed_at.isoformat(),
            "restaurant": {
                "cash": float(cash_total),
                "chapa": float(chapa_total),
                "telebirr": float(telebirr_total),
                "card": float(card_total),
                "total": float(restaurant_total),
                "order_count": paid_orders.count(),
            },
            "rooms": {
                "revenue": float(room_revenue),
                "checkouts": checked_out_today.count(),
            },
            "grand_total": float(grand_total),
            "is_closed": True,
            "hotel_name": get_system_settings().hotel_name,
            "tin_number": get_system_settings().tin_number,
            "printer_paper_size": get_system_settings().printer_paper_size,
        })


class OccupancyReportView(APIView):
    """Occupancy %, RevPAR, ADR, and total revenue."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if request.user.role not in ["admin", "reception"]:
            return Response({"error": "Access denied."}, status=403)
        total_rooms = Room.objects.count()
        occupied = Room.objects.filter(status="Occupied").count()
        reserved = Room.objects.filter(status="Reserved").count()
        cleaning = Room.objects.filter(status="Cleaning").count()
        maintenance = Room.objects.filter(status="Maintenance").count()
        available = Room.objects.filter(status="Available").count()

        occupancy_pct = round((occupied / total_rooms * 100), 1) if total_rooms else 0

        # Revenue from room history (last 30 days)
        from datetime import timedelta
        thirty_days_ago = timezone.now().date() - timedelta(days=30)
        history = RoomHistory.objects.filter(event_type="checkout", created_at__date__gte=thirty_days_ago)
        total_rev = sum(to_decimal(h.revenue) for h in history)
        checkout_count = history.count()
        adr = float(total_rev / checkout_count) if checkout_count else 0
        revpar = round(adr * (occupancy_pct / 100), 2) if adr else 0

        # Today's audit if exists
        today = timezone.now().date()
        today_audit = DayAuditLog.objects.filter(audit_date=today).first()

        return Response({
            "total_rooms": total_rooms,
            "occupied": occupied,
            "reserved": reserved,
            "cleaning": cleaning,
            "maintenance": maintenance,
            "available": available,
            "occupancy_percent": occupancy_pct,
            "total_revenue_30d": float(total_rev),
            "adr": round(adr, 2),
            "revpar": revpar,
            "checkout_count_30d": checkout_count,
            "today_audit": DayAuditLogSerializer(today_audit).data if today_audit else None,
        })
