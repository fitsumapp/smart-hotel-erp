"""Orders API views extracted from the legacy facade."""
# Shared imports and compatibility helpers live in users.views during migration.
from users.views import *  # noqa: F401,F403
import users.views as legacy_views
from .services import create_order_idempotently
from hotel.integrity import transition_order


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
                table_id=data.get("table_id"), items=data.get("items", []),
                waiter=request.user, idempotency_key=request.headers.get("Idempotency-Key"),
            )
            return Response(
                {"message": "Order sent to kitchen!", "order_id": order.id, "created": created},
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
            )
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class KitchenOrdersView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        orders = (
            Order.objects.filter(status__in=["pending", "preparing"])
            .select_related("table")
            .prefetch_related("items__menu_item")
            .order_by("created_at")
        )
        return Response(OrderSerializer(orders, many=True).data)


class UpdateOrderStatusView(APIView):
    permission_classes = [IsKitchenBarOrAdmin]

    def post(self, request, order_id):
        try:
            new_status = request.data.get("status")
            if new_status not in dict(Order.ORDER_STATUS):
                return Response({"error": "Invalid order status."}, status=400)

            with transaction.atomic():
                order = (
                    Order.objects.select_for_update()
                    .select_related("table")
                    .get(id=order_id)
                )
                allowed = ORDER_STATUS_TRANSITIONS.get(order.status, set())
                if new_status not in allowed:
                    return Response(
                        {"error": f"Cannot transition order from {order.status} to {new_status}."},
                        status=400,
                    )
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
        except Exception as exc:
            logger.exception("Order status update failed")
            return Response({"error": "Unable to update order status."}, status=500)


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
    permission_classes = [IsHotelAdmin]

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


class CashierOrderProcessView(APIView):
    permission_classes = [IsCashierOrAdmin]

    def post(self, request, order_id):
        try:
            with transaction.atomic():
                order = (
                    Order.objects.select_for_update()
                    .prefetch_related("items__menu_item")
                    .select_related("table")
                    .get(id=order_id)
                )
                finalize_paid_order(
                    order,
                    payment_method=request.data.get("payment_method", "Cash"),
                    payment_reference=request.data.get(
                        "payment_reference", f"POS-{order.id}-{timezone.now().strftime('%H%M%S')}"
                    ),
                    tip_amount=request.data.get("tip_amount", order.tip_amount),
                    cashier=request.user,
                )
        except Order.DoesNotExist:
            return Response({"error": "Order not found"}, status=404)

        summary = build_payment_summary(order)
        return Response({"message": "Payment processed successfully!", "receipt_data": summary})


class CashierPendingBillsView(APIView):
    permission_classes = [IsCashierOrAdmin]

    def get(self, request):
        orders = (
            Order.objects.filter(
                status__in=["bill_requested", "served"],
                payment_status="pending",
            )
            .select_related("table")
            .prefetch_related("items__menu_item")
            .order_by("-updated_at")
        )
        return Response(OrderSerializer(orders, many=True).data)


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
            order = Order.objects.prefetch_related("items__menu_item").select_related("table").get(id=order_id)
        except Order.DoesNotExist:
            return Response({"error": "Order not found"}, status=404)

        # Ethiopian law: receipt must be printed BEFORE payment — no payment check here
        # Ensure financials are up-to-date before printing
        sync_order_financials(order)

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
                "waiter_name": order.waiter_username or (User.objects.filter(id=order.waiter_id_ref).values_list("username", flat=True).first() if order.waiter_id_ref else ""),
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


