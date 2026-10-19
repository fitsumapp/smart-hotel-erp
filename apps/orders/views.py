"""Orders API views extracted from the legacy facade."""
# Shared imports and compatibility helpers live in users.views during migration.
from users.views import *  # noqa: F401,F403
import users.views as legacy_views
from .services import create_order_idempotently, settle_dining_session, build_session_payment_summary
from hotel.integrity import transition_order
from hotel.models import DiningSession
from .serializers import DiningSessionSerializer


def finalize_paid_order(*args, **kwargs):
    return legacy_views.finalize_paid_order(*args, **kwargs)


from users.permissions import IsAdminOrReadOnly
from .selectors import select_admin_orders

class CategoryViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrReadOnly]
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class MenuItemViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrReadOnly]
    queryset = MenuItem.objects.all()
    serializer_class = MenuItemSerializer


class RestaurantTableViewSet(viewsets.ModelViewSet):
    serializer_class = RestaurantTableSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return RestaurantTable.objects.all().order_by("table_code")


class DashboardStatsView(APIView):
    permission_classes = [IsHotelAdmin]

    def get(self, request):
        from django.db.models import Sum, Count, Q
        from datetime import date

        today = date.today()

        # ── POS / Orders ──────────────────────────────────────────────────────
        paid_orders = Order.objects.filter(payment_status="paid")
        pos_revenue = float(paid_orders.aggregate(t=Sum("total_amount"))["t"] or 0)
        pos_tips    = float(paid_orders.aggregate(t=Sum("tip_amount"))["t"] or 0)
        total_orders   = Order.objects.count()
        pending_orders = Order.objects.filter(status="pending").count()
        today_orders   = Order.objects.filter(created_at__date=today).count()
        today_revenue  = float(
            Order.objects.filter(payment_status="paid", created_at__date=today)
                         .aggregate(t=Sum("total_amount"))["t"] or 0
        )

        # ── Rooms / Front Office ──────────────────────────────────────────────
        total_rooms     = Room.objects.count()
        available_rooms = Room.objects.filter(status="Available").count()
        occupied_rooms  = Room.objects.filter(status="Occupied").count()
        maintenance_rooms = Room.objects.filter(status="Maintenance").count()
        cleaning_rooms  = Room.objects.filter(status="Cleaning").count()
        reserved_rooms  = Room.objects.filter(status="Reserved").count()
        occupancy_pct   = round((occupied_rooms / total_rooms * 100), 1) if total_rooms else 0

        # Active / today's reservations
        active_reservations    = Reservation.objects.filter(status__in=["confirmed", "checked_in"]).count()
        checkins_today         = Reservation.objects.filter(check_in_date=today, status="confirmed").count()
        checkouts_today        = Reservation.objects.filter(check_out_date=today, status="checked_in").count()
        room_revenue           = float(
            Reservation.objects.filter(payment_status="paid")
                               .aggregate(t=Sum("total_amount"))["t"] or 0
        )

        # ── Inventory ────────────────────────────────────────────────────────
        total_items      = InventoryItem.objects.count()
        low_stock_items  = InventoryItem.objects.filter(
            current_stock__lte=models.F("min_reorder_level")
        ).count()
        from django.db.models import F, Sum, ExpressionWrapper, DecimalField
        inventory_value = float(
            InventoryItem.objects.aggregate(
                total=Sum(
                    ExpressionWrapper(
                        F("current_stock") * F("unit_cost"),
                        output_field=DecimalField(max_digits=18, decimal_places=2),
                    )
                )
            )["total"] or 0
        )

        # ── Finance ───────────────────────────────────────────────────────────
        total_income   = float(
            JournalEntryItem.objects.filter(account__account_type="revenue")
                                    .aggregate(t=Sum("amount_credit"))["t"] or 0
        )
        total_expenses = float(
            ExpenseTransaction.objects.aggregate(t=Sum("amount"))["t"] or 0
        )
        net_profit = total_income - total_expenses

        # ── Staff ─────────────────────────────────────────────────────────────
        total_staff = User.objects.filter(is_active=True).exclude(role="customer").count()

        data = {
            "pos": {
                "totalOrders":   total_orders,
                "pendingOrders": pending_orders,
                "todayOrders":   today_orders,
                "revenue":       pos_revenue,
                "todayRevenue":  today_revenue,
                "tips":          pos_tips,
            },
            "rooms": {
                "total":       total_rooms,
                "available":   available_rooms,
                "occupied":    occupied_rooms,
                "maintenance": maintenance_rooms,
                "cleaning":    cleaning_rooms,
                "reserved":    reserved_rooms,
                "occupancyPct": occupancy_pct,
            },
            "reservations": {
                "active":         active_reservations,
                "checkInsToday":  checkins_today,
                "checkOutsToday": checkouts_today,
                "roomRevenue":    room_revenue,
            },
            "inventory": {
                "totalItems":     total_items,
                "lowStockAlerts": low_stock_items,
                "totalValue":     inventory_value,
            },
            "finance": {
                "totalIncome":   total_income,
                "totalExpenses": total_expenses,
                "netProfit":     net_profit,
            },
            "staff": {
                "totalActive": total_staff,
            },
        }
        return Response(data)


class CreateOrderView(APIView):
    permission_classes = [IsWaiterOrAdmin]

    def post(self, request):
        data = request.data
        try:
            order, created = create_order_idempotently(
                table_id=data.get("table_id"),
                items=data.get("items", []),
                waiter=request.user,
                idempotency_key=request.headers.get("Idempotency-Key"),
                session_id=data.get("session_id"),
            )
            return Response(
                {
                    "message": "Order sent to kitchen!",
                    "order_id": order.id,
                    "session_id": order.session_id,
                    "created": created,
                },
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
            )
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


PREPARATION_STATUS_TRANSITIONS = {
    "pending": {"preparing"},
    "preparing": {"ready"},
}


class KitchenOrdersView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        station = request.query_params.get("station")
        orders = (
            Order.objects.filter(status__in=["pending", "preparing"])
            .select_related("table")
            .prefetch_related("items__menu_item__category")
            .order_by("created_at")
        )

        serializer = OrderSerializer(
            orders,
            many=True,
            context={"station": station} if station else None
        )
        data = [
            order_data for order_data in serializer.data
            if not station or (
                len(order_data.get("items", [])) > 0
                and any(it.get("status") in ["pending", "preparing"] for it in order_data.get("items", []))
            )
        ]
        return Response(data)


class UpdateOrderStatusView(APIView):
    permission_classes = [IsKitchenBarOrAdmin]

    def post(self, request, order_id):
        try:
            new_status = request.data.get("status")
            if not new_status or new_status not in dict(Order.ORDER_STATUS):
                return Response({"error": "Invalid order status."}, status=status.HTTP_400_BAD_REQUEST)

            # Preparation transitions can only move to 'preparing' or 'ready'
            if new_status not in ["preparing", "ready"]:
                return Response(
                    {"error": f"Cannot transition order to {new_status}."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            station_req = request.data.get("station")
            item_id_req = request.data.get("item_id")
            user_role = getattr(request.user, "role", "")

            # Role-based station authorization
            if user_role == "kitchen":
                if station_req and station_req.lower() != "kitchen":
                    return Response({"error": "Kitchen staff cannot update Bar orders."}, status=status.HTTP_403_FORBIDDEN)
                target_station = "Kitchen"
            elif user_role == "bar":
                if station_req and station_req.lower() != "bar":
                    return Response({"error": "Bar staff cannot update Kitchen orders."}, status=status.HTTP_403_FORBIDDEN)
                target_station = "Bar"
            else:
                # Hotel Admin or superuser override
                target_station = station_req.strip() if station_req else None

            with transaction.atomic():
                order = (
                    Order.objects.select_for_update()
                    .select_related("table")
                    .prefetch_related("items__menu_item__category")
                    .get(id=order_id)
                )

                if order.status in ["served", "paid", "cancelled"]:
                    return Response(
                        {"error": f"Cannot transition order from {order.status} to {new_status}."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                all_items = list(order.items.all())

                # Filter target items by item_id or target_station
                if item_id_req:
                    target_items = [it for it in all_items if it.id == int(item_id_req)]
                    if not target_items:
                        return Response({"error": "Order item not found."}, status=status.HTTP_404_NOT_FOUND)
                    it_station = target_items[0].get_station().lower()
                    if user_role == "kitchen" and it_station == "bar":
                        return Response({"error": "Kitchen staff cannot update Bar items."}, status=status.HTTP_403_FORBIDDEN)
                    if user_role == "bar" and it_station != "bar":
                        return Response({"error": "Bar staff cannot update Kitchen items."}, status=status.HTTP_403_FORBIDDEN)
                elif target_station:
                    st_lower = target_station.lower()
                    if st_lower == "bar":
                        target_items = [it for it in all_items if it.get_station().lower() == "bar"]
                    elif st_lower == "kitchen":
                        target_items = [it for it in all_items if it.get_station().lower() != "bar"]
                    else:
                        target_items = [it for it in all_items if it.get_station().lower() == st_lower]

                    if not target_items and all_items:
                        return Response(
                            {"error": f"No items belonging to '{target_station}' found in this order."},
                            status=status.HTTP_403_FORBIDDEN if user_role in ["kitchen", "bar"] else status.HTTP_400_BAD_REQUEST,
                        )
                else:
                    target_items = all_items

                # Validate transitions
                if not target_items:
                    allowed = ORDER_STATUS_TRANSITIONS.get(order.status, set())
                    if new_status not in allowed:
                        return Response(
                            {"error": f"Cannot transition order from {order.status} to {new_status}."},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    order.status = new_status
                    order.save(update_fields=["status", "updated_at"])
                else:
                    for it in target_items:
                        if it.status == new_status:
                            continue
                        allowed = PREPARATION_STATUS_TRANSITIONS.get(it.status, set())
                        if new_status not in allowed:
                            return Response(
                                {"error": f"Cannot transition order from {it.status} to {new_status}."},
                                status=status.HTTP_400_BAD_REQUEST,
                            )

                    for it in target_items:
                        it.status = new_status
                        it.save(update_fields=["status"])

                    # Recompute overall order status
                    fresh_items = list(order.items.all())
                    if all(it.status == "ready" for it in fresh_items):
                        order.status = "ready"
                    elif any(it.status in ["preparing", "ready"] for it in fresh_items):
                        order.status = "preparing"
                    else:
                        order.status = "pending"
                    order.save(update_fields=["status", "updated_at"])

            if order.status == "ready" and order.waiter_id_ref:
                Notification.objects.create(
                    user_id_ref=order.waiter_id_ref,
                    message=(
                        f"Order #ORD-{order.id} (Table {order.table.table_code}) "
                        f"is ready. Please serve the customer."
                    ),
                )

            return Response({"message": f"Order status updated to {new_status}"})
        except Order.DoesNotExist:
            return Response({"error": "Order not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as exc:
            logger.exception("Order status update failed")
            return Response({"error": "Unable to update order status."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


_WAITER_STATUS_PRIORITY = {
    "ready": 0,
    "pending": 1,
    "preparing": 2,
    "served": 3,
    "bill_requested": 4,
}


class WaiterOrdersView(APIView):
    permission_classes = [IsWaiterOrAdmin]

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
        # Cache settings to avoid repeated DB lookups in sync loop
        cached_settings = get_system_settings()
        for order in orders:
            sync_order_financials(order, settings_obj=cached_settings, save=False)
        return Response(OrderSerializer(orders, many=True).data)


class MarkOrderServedView(APIView):
    permission_classes = [IsWaiterOrAdmin]

    def post(self, request, order_id):
        try:
            owned = Order.objects.get(id=order_id, waiter_id_ref=request.user.id)
            order, _ = transition_order(order_id=owned.pk, to_status="served")

            # Notify all cashiers to print receipt and collect payment
            notify_cashiers(
                f"Order Served — Print Receipt: Table {order.table.table_code} / ORD-{order.id}"
            )

            return Response({"message": "Order marked as served!"})
        except Order.DoesNotExist:
            return Response({"error": "Order not found"}, status=404)
        except Exception as exc:
            logger.exception("Mark order served failed")
            return Response({"error": "Unable to mark order as served."}, status=500)


class RequestBillView(APIView):
    permission_classes = [IsWaiterOrAdmin]

    def post(self, request, order_id):
        try:
            owned = Order.objects.get(id=order_id, waiter_id_ref=request.user.id)
            order, _ = transition_order(order_id=owned.pk, to_status="bill_requested")
            sync_order_financials(order)
            message = f"Bill requested for Table {order.table.table_code}. Please process payment."
            cashiers = User.objects.filter(role="cashier", is_active=True)
            if cashiers.exists():
                notify_users(cashiers, message)
            else:
                Notification.objects.create(user_id_ref=request.user.id, message=message)
            return Response({"message": "Bill request sent successfully!"})
        except Order.DoesNotExist:
            return Response({"error": "Order not found"}, status=404)
        except Exception as exc:
            logger.exception("Bill request failed")
            return Response({"error": "Unable to request bill."}, status=500)


class CompleteOrderView(APIView):
    permission_classes = [IsCashierOrAdmin]

    def post(self, request, order_id):
        try:
            with transaction.atomic():
                order = (
                    Order.objects.select_for_update()
                    .select_related("table")
                    .get(id=order_id)
                )
                finalize_paid_order(
                    order,
                    payment_method=request.data.get("payment_method", "Cash"),
                    payment_reference=request.data.get("payment_reference", f"CASH-{order.id}"),
                    tip_amount=request.data.get("tip_amount", order.tip_amount),
                    cashier=request.user,
                )
                return Response({"message": "Payment completed. Table is now available!"})
        except Order.DoesNotExist:
            return Response({"error": "Order not found"}, status=404)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class NotificationView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # Limit to 100 most recent to stay fast on high-volume days
        notifs = (
            Notification.objects.filter(user_id_ref=request.user.id)
            .order_by("-created_at")[:100]
        )
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


class SystemSettingsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(SystemSettingsSerializer(get_system_settings()).data)

    def post(self, request):
        if request.user.role != "admin" and not request.user.is_superuser:
            return Response({"error": "Only admins can modify system settings."}, status=403)
        settings_obj = get_system_settings()
        data = request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
        if not request.user.is_superuser:
            for mod_field in ["module_rooms", "module_pos", "module_inventory", "module_finance"]:
                data.pop(mod_field, None)
        serializer = SystemSettingsSerializer(settings_obj, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)


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
    permission_classes = [IsWaiterOrAdmin]

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
    permission_classes = [IsWaiterOrAdmin]

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
                "payment_page_url": create_payment_page_url(order, request=request),
                "token": order.payment_page_token,
                "summary": build_payment_summary(order),
            }
        )


class OccupiedRoomsListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from hotel.models import Reservation
        active_res = (
            Reservation.objects.filter(status="checked_in")
            .select_related("room")
            .order_by("room__room_number")
        )
        data = [
            {
                "reservation_id": r.id,
                "room_id": r.room.id if r.room else None,
                "room_number": r.room.room_number if r.room else "N/A",
                "room_name": r.room.name if r.room else "",
                "room_type": r.room.room_type if r.room else "",
                "guest_name": r.guest_name,
                "guest_phone": r.guest_phone,
                "check_in_date": r.check_in_date.isoformat() if r.check_in_date else None,
                "check_out_date": r.check_out_date.isoformat() if r.check_out_date else None,
            }
            for r in active_res
        ]
        return Response(data)


class RoomChargeProcessView(APIView):
    permission_classes = [IsWaiterOrAdmin]

    def post(self, request, order_id):
        reservation_id = request.data.get("reservation_id")
        room_number = request.data.get("room_number")
        from hotel.models import Reservation
        reservation = None
        if reservation_id:
            reservation = Reservation.objects.filter(id=reservation_id, status="checked_in").select_related("room").first()
        elif room_number:
            reservation = Reservation.objects.filter(room__room_number=room_number, status="checked_in").select_related("room").first()

        if not reservation:
            return Response({"error": "Active checked-in reservation not found for this room."}, status=404)

        try:
            with transaction.atomic():
                order = (
                    Order.objects.select_for_update()
                    .prefetch_related("items__menu_item")
                    .select_related("table")
                    .get(id=order_id)
                )
                if order.payment_status == "paid":
                    return Response({"error": "Order is already paid."}, status=400)

                finalize_paid_order(
                    order,
                    payment_method="Room Charge",
                    payment_reference=f"Room {reservation.room.room_number if reservation.room else ''} - {reservation.guest_name}",
                    tip_amount=request.data.get("tip_amount", order.tip_amount),
                    cashier=request.user,
                    reservation=reservation,
                )
        except Order.DoesNotExist:
            return Response({"error": "Order not found"}, status=404)

        summary = build_payment_summary(order)
        return Response({
            "message": f"Order #{order.id} charged to Room {reservation.room.room_number if reservation.room else ''} successfully!",
            "receipt_data": summary,
            "room_number": reservation.room.room_number if reservation.room else "",
            "guest_name": reservation.guest_name,
        })


class CashierOrderProcessView(APIView):
    permission_classes = [IsCashierOrAdmin]

    def post(self, request, order_id):
        try:
            with transaction.atomic():
                order = (
                    Order.objects.select_for_update()
                    .prefetch_related("items__menu_item")
                    .select_related("table", "session")
                    .get(id=order_id)
                )
                if order.payment_status == "paid":
                    return Response({"error": "Order is already marked as paid."}, status=400)

                payment_method = request.data.get("payment_method", "Cash")
                reservation_id = request.data.get("reservation_id")
                reservation_obj = None
                if reservation_id or str(payment_method).lower() in ["room charge", "room_charge", "room"]:
                    from hotel.models import Reservation
                    if reservation_id:
                        reservation_obj = Reservation.objects.filter(id=reservation_id, status="checked_in").select_related("room").first()
                    elif request.data.get("room_number"):
                        reservation_obj = Reservation.objects.filter(room__room_number=request.data.get("room_number"), status="checked_in").select_related("room").first()

                    if not reservation_obj:
                        return Response({"error": "No active checked-in guest found for the selected room."}, status=400)

                settle_session_flag = request.data.get("settle_session", True)
                if order.session and settle_session_flag:
                    session, settled_orders = settle_dining_session(
                        order.session,
                        payment_method=payment_method,
                        payment_reference=request.data.get(
                            "payment_reference", f"POS-SESS-{order.session.id}-{timezone.now().strftime('%H%M%S')}"
                        ),
                        tip_amount=request.data.get("tip_amount", order.tip_amount),
                        cashier=request.user,
                        reservation=reservation_obj,
                    )
                    summary = build_session_payment_summary(session)
                    return Response({
                        "message": f"Dining session #{session.id} payment processed successfully!",
                        "receipt_data": summary,
                        "session_id": session.id,
                        "orders_settled": [o.id for o in settled_orders],
                    })
                else:
                    finalize_paid_order(
                        order,
                        payment_method=payment_method,
                        payment_reference=request.data.get(
                            "payment_reference", f"POS-{order.id}-{timezone.now().strftime('%H%M%S')}"
                        ),
                        tip_amount=request.data.get("tip_amount", order.tip_amount),
                        cashier=request.user,
                        reservation=reservation_obj,
                    )
                    summary = build_payment_summary(order)
                    return Response({"message": "Payment processed successfully!", "receipt_data": summary})
        except Order.DoesNotExist:
            return Response({"error": "Order not found"}, status=404)
        except Exception as exc:
            logger.exception("Cashier payment failed")
            return Response({"error": str(exc)}, status=400)


class CashierPendingBillsView(APIView):
    permission_classes = [IsCashierOrAdmin]

    def get(self, request):
        active_session_ids = list(
            Order.objects.filter(
                status__in=["bill_requested", "served"],
                payment_status="pending",
                session__isnull=False,
                session__status="active",
            )
            .values_list("session_id", flat=True)
            .distinct()
        )

        session_orders = list(
            Order.objects.filter(
                session_id__in=active_session_ids,
                payment_status="pending",
            )
            .exclude(status="cancelled")
            .select_related("table", "session")
            .prefetch_related("items__menu_item__category")
            .order_by("created_at")
        )

        standalone_orders = list(
            Order.objects.filter(
                session__isnull=True,
                status__in=["bill_requested", "served"],
                payment_status="pending",
            )
            .select_related("table")
            .prefetch_related("items__menu_item__category")
            .order_by("-updated_at")
        )

        sessions_map = {}
        for ord_obj in session_orders:
            if ord_obj.session_id not in sessions_map:
                sessions_map[ord_obj.session_id] = []
            sessions_map[ord_obj.session_id].append(ord_obj)

        consolidated_bills = []

        for sess_id, sess_orders in sessions_map.items():
            primary_order = sess_orders[0]
            session_obj = primary_order.session

            all_items = []
            sub_total = Decimal("0.00")
            service_charge = Decimal("0.00")
            vat = Decimal("0.00")
            total = Decimal("0.00")
            tip = Decimal("0.00")

            order_summaries = []
            for o in sess_orders:
                sub_total += to_decimal(o.sub_total)
                service_charge += to_decimal(o.service_charge_amount)
                vat += to_decimal(o.vat_amount)
                total += to_decimal(o.total_amount)
                tip += to_decimal(o.tip_amount)
                order_summaries.append({
                    "id": o.id,
                    "status": o.status,
                    "total_amount": float(o.total_amount),
                    "created_at": o.created_at,
                })
                for it in o.items.all():
                    all_items.append({
                        "id": it.id,
                        "order_id": o.id,
                        "menu_item": it.menu_item_id,
                        "menu_item_name": it.menu_item.name if it.menu_item else "",
                        "category_name": it.menu_item.category.name if it.menu_item and it.menu_item.category else "",
                        "station": it.get_station(),
                        "quantity": it.quantity,
                        "price_at_order": float(it.price_at_order),
                        "status": it.status,
                        "notes": it.notes,
                    })

            sess_status = "bill_requested" if any(o.status == "bill_requested" for o in sess_orders) else "served"

            bill_data = {
                "id": primary_order.id,
                "session_id": sess_id,
                "is_session": True,
                "rounds_count": len(sess_orders),
                "orders": order_summaries,
                "table": primary_order.table_id,
                "table_code": primary_order.table.table_code if primary_order.table else "",
                "waiter_id_ref": primary_order.waiter_id_ref,
                "waiter_name": primary_order.waiter_username or (session_obj.opened_by_username if session_obj else ""),
                "items": all_items,
                "sub_total": float(sub_total),
                "service_charge_amount": float(service_charge),
                "vat_amount": float(vat),
                "total_amount": float(total),
                "grand_total": float(total),
                "tip_amount": float(tip),
                "status": sess_status,
                "payment_status": "pending",
                "payment_method": primary_order.payment_method,
                "payment_reference": primary_order.payment_reference,
                "created_at": session_obj.created_at if session_obj else primary_order.created_at,
            }
            consolidated_bills.append(bill_data)

        if standalone_orders:
            standalone_data = OrderSerializer(standalone_orders, many=True).data
            consolidated_bills.extend(standalone_data)

        return Response(consolidated_bills)


class CashierCompletedBillsView(APIView):
    permission_classes = [IsCashierOrAdmin]

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


class AdminOrdersView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if request.user.role not in ["admin", "finance"] and not request.user.is_superuser:
            return Response({"error": "Forbidden: Admin or Finance role required."}, status=status.HTTP_403_FORBIDDEN)

        orders = select_admin_orders(request.query_params)
        paginator = V1PageNumberPagination()
        page = paginator.paginate_queryset(orders, request, view=self)
        if page is not None:
            return paginator.get_paginated_response(OrderSerializer(page, many=True).data)


        limit = request.query_params.get("limit")
        if limit:
            try:
                orders = orders[: min(max(int(limit), 1), 100)]
            except ValueError:
                pass
        return Response(OrderSerializer(orders, many=True).data)


class CashierReceiptView(APIView):
    permission_classes = [IsCashierOrAdmin]

    def get(self, request, order_id):
        try:
            order = (
                Order.objects.prefetch_related("items__menu_item")
                .select_related("table", "session")
                .get(id=order_id)
            )
        except Order.DoesNotExist:
            return Response({"error": "Order not found"}, status=404)

        sync_order_financials(order)
        settings_obj = get_system_settings()

        if order.session:
            session_orders = list(
                order.session.orders.exclude(status="cancelled")
                .prefetch_related("items__menu_item")
                .all()
                .order_by("created_at")
            )
            for o in session_orders:
                sync_order_financials(o)

            items_data = []
            sub_total = Decimal("0.00")
            service_charge = Decimal("0.00")
            vat = Decimal("0.00")
            grand_total = Decimal("0.00")
            tip_amount = Decimal("0.00")

            paid_total = Decimal("0.00")
            unpaid_total = Decimal("0.00")

            for o in session_orders:
                sub_total += to_decimal(o.sub_total)
                service_charge += to_decimal(o.service_charge_amount)
                vat += to_decimal(o.vat_amount)
                grand_total += to_decimal(o.total_amount)
                tip_amount += to_decimal(o.tip_amount)
                ord_tot = to_decimal(o.total_amount) + to_decimal(o.tip_amount)
                if o.payment_status == "paid":
                    paid_total += ord_tot
                else:
                    unpaid_total += ord_tot

                for it in o.items.all():
                    items_data.append({
                        "menu_item_name": it.menu_item.name if it.menu_item else "Item",
                        "quantity": it.quantity,
                        "price_at_order": float(it.price_at_order),
                        "notes": it.notes,
                        "round_order_id": o.id,
                    })

            return Response({
                "order_id": order.id,
                "session_id": order.session_id,
                "rounds_count": len(session_orders),
                "table_code": order.table.table_code if order.table else "",
                "waiter_name": order.waiter_username or (order.session.opened_by_username if order.session else ""),
                "items": items_data,
                "sub_total": float(sub_total),
                "service_charge": float(service_charge),
                "vat": float(vat),
                "grand_total": float(grand_total),
                "tip_amount": float(tip_amount),
                "paid_amount": float(paid_total),
                "outstanding_balance": float(unpaid_total),
                "amount_due": float(unpaid_total),
                "payment_method": order.payment_method or "Cash",
                "payment_reference": order.payment_reference or "",
                "processed_at": order.updated_at.isoformat(),
                "fiscal_number": f"FS{order.id:06d}",
                "tin_number": settings_obj.tin_number,
                "address": settings_obj.address,
                "phone_number": settings_obj.phone_number,
                "fiscal_machine_no": settings_obj.fiscal_machine_no,
            })
        else:
            items_data = [
                {
                    "menu_item_name": item.menu_item.name if item.menu_item else "Item",
                    "quantity": item.quantity,
                    "price_at_order": float(item.price_at_order),
                    "notes": item.notes,
                }
                for item in order.items.all()
            ]

            order_tot = float(order.total_amount) + float(order.tip_amount)
            is_paid = order.payment_status == "paid"

            return Response(
                {
                    "order_id": order.id,
                    "table_code": order.table.table_code if order.table else "",
                    "waiter_name": order.waiter_username or (User.objects.filter(id=order.waiter_id_ref).values_list("username", flat=True).first() if order.waiter_id_ref else ""),
                    "items": items_data,
                    "sub_total": float(order.sub_total),
                    "service_charge": float(order.service_charge_amount),
                    "vat": float(order.vat_amount),
                    "grand_total": float(order.total_amount),
                    "tip_amount": float(order.tip_amount),
                    "paid_amount": order_tot if is_paid else 0.0,
                    "outstanding_balance": 0.0 if is_paid else order_tot,
                    "amount_due": 0.0 if is_paid else order_tot,
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


class ActiveDiningSessionsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        sessions = (
            DiningSession.objects.filter(status="active")
            .select_related("table")
            .prefetch_related("orders__items__menu_item")
            .order_by("-created_at")
        )
        return Response(DiningSessionSerializer(sessions, many=True).data)


class DiningSessionDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, session_id):
        try:
            session = (
                DiningSession.objects.select_related("table")
                .prefetch_related("orders__items__menu_item")
                .get(id=session_id)
            )
            return Response(DiningSessionSerializer(session).data)
        except DiningSession.DoesNotExist:
            return Response({"error": "Dining session not found"}, status=status.HTTP_404_NOT_FOUND)


class SettleDiningSessionView(APIView):
    permission_classes = [IsCashierOrAdmin]

    def post(self, request, session_id):
        try:
            with transaction.atomic():
                session = DiningSession.objects.select_for_update().select_related("table").get(id=session_id)
                payment_method = request.data.get("payment_method", "Cash")
                reservation_id = request.data.get("reservation_id")
                reservation_obj = None
                if reservation_id or str(payment_method).lower() in ["room charge", "room_charge", "room"]:
                    from hotel.models import Reservation
                    if reservation_id:
                        reservation_obj = Reservation.objects.filter(id=reservation_id, status="checked_in").select_related("room").first()
                    elif request.data.get("room_number"):
                        reservation_obj = Reservation.objects.filter(room__room_number=request.data.get("room_number"), status="checked_in").select_related("room").first()

                    if not reservation_obj:
                        return Response({"error": "No active checked-in guest found for the selected room."}, status=400)

                session, settled_orders = settle_dining_session(
                    session,
                    payment_method=payment_method,
                    payment_reference=request.data.get(
                        "payment_reference", f"SESS-{session.id}-{timezone.now().strftime('%H%M%S')}"
                    ),
                    tip_amount=request.data.get("tip_amount", 0),
                    cashier=request.user,
                    reservation=reservation_obj,
                )
                summary = build_session_payment_summary(session)
                return Response({
                    "message": f"Dining session #{session.id} settled successfully. Table {session.table.table_code} is now available!",
                    "receipt_data": summary,
                    "orders_settled": [o.id for o in settled_orders],
                })
        except DiningSession.DoesNotExist:
            return Response({"error": "Dining session not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as exc:
            logger.exception("Settle dining session failed")
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


