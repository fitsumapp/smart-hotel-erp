"""Reporting API views extracted from the legacy facade."""
# Shared imports and compatibility helpers live in users.views during migration.
from users.views import *  # noqa: F401,F403
from core.performance import bounded_date_range, datetime_bounds

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

        # Room revenue (collected today) broken down by payment method
        room_transactions = RoomHistory.objects.filter(event_type__in=["checkin", "checkout"], created_at__date=report_date)
        room_revenue = sum(to_decimal(r.revenue) for r in room_transactions)
        room_cash = sum(to_decimal(r.revenue) for r in room_transactions if r.payment_method == "Cash")
        room_digital = sum(to_decimal(r.revenue) for r in room_transactions if r.payment_method == "Digital Payment")
        room_bank = sum(to_decimal(r.revenue) for r in room_transactions if r.payment_method == "Bank Transfer")

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
                "cash": float(room_cash),
                "digital": float(room_digital),
                "bank_transfer": float(room_bank),
                "checkouts": room_transactions.filter(event_type="checkout").count(),
                "checkins": room_transactions.filter(event_type="checkin").count(),
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

        room_transactions = RoomHistory.objects.filter(event_type__in=["checkin", "checkout"], created_at__date=report_date)
        checked_out_today = room_transactions.filter(event_type="checkout")
        room_revenue = sum(to_decimal(r.revenue) for r in room_transactions)
        room_cash = sum(to_decimal(r.revenue) for r in room_transactions if r.payment_method == "Cash")
        room_digital = sum(to_decimal(r.revenue) for r in room_transactions if r.payment_method == "Digital Payment")
        room_bank = sum(to_decimal(r.revenue) for r in room_transactions if r.payment_method == "Bank Transfer")
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
                "cash": float(room_cash),
                "digital": float(room_digital),
                "bank_transfer": float(room_bank),
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


class FinanceDashboardStatsView(APIView):
    """
    Consolidated Hotel Finance Page view.
    Calculates Revenue (Rooms, F&B, Folio Extras), Expenses (Ingredient purchases),
    Profit, Receivables, Daily Trends, and Transactions Log with date range filtering.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from django.db import connection
        from django.db.models import Sum, F, ExpressionWrapper, DecimalField
        from django.db.models.functions import TruncDate
        from django.utils import timezone
        from datetime import datetime, date, timedelta
        from decimal import Decimal
        
        # Enforce Admin/Finance Role checking
        if request.user.role not in ["admin", "finance"] and not request.user.is_superuser:
            return Response(
                {"error": "Access denied. Only hotel administrators or finance staff can access financial records."},
                status=status.HTTP_403_FORBIDDEN
            )
            


        # Parse date range params
        # Default start_date to first day of the current month
        today_date = timezone.now().date()
        default_start = today_date.replace(day=1)
        
        start_date_str = request.query_params.get("start_date")
        end_date_str = request.query_params.get("end_date")
        
        start_date, end_date = bounded_date_range(
            request.query_params,
            default_start=default_start,
            default_end=today_date,
            max_days=366,
        )
        start_dt, end_dt = datetime_bounds(start_date, end_date)

        # -- 1. REVENUE CALCULATIONS --
        # Room Revenue: sum of all revenue recorded in RoomHistory checkin/checkout transactions
        room_rev_query = RoomHistory.objects.filter(
            created_at__gte=start_dt, created_at__lt=end_dt
        ).aggregate(total=Sum("revenue"))
        room_revenue = to_decimal(room_rev_query["total"])

        # F&B Revenue: sum of total paid orders (restaurant/bar)
        fb_rev_query = Order.objects.filter(
            payment_status="paid",
            updated_at__gte=start_dt, updated_at__lt=end_dt
        ).aggregate(total=Sum("total_amount"))
        fb_revenue = to_decimal(fb_rev_query["total"])

        # Extra Charges / Folios: sum of folio charges (e.g. laundry, minibar)
        folio_rev_query = FolioCharge.objects.filter(
            added_at__gte=start_dt, added_at__lt=end_dt
        ).aggregate(total=Sum("amount"))
        folio_revenue = to_decimal(folio_rev_query["total"])

        total_revenue = room_revenue + fb_revenue + folio_revenue

        # -- 2. EXPENSE CALCULATIONS --
        # Expenses are inventory purchases (StockTransactions of type 'purchase')
        expense_query = StockTransaction.objects.filter(
            transaction_type="purchase",
            timestamp__gte=start_dt, timestamp__lt=end_dt
        ).annotate(
            cost=ExpressionWrapper(F("quantity") * F("unit_cost"), output_field=DecimalField(max_digits=12, decimal_places=2))
        ).aggregate(total=Sum("cost"))
        total_expenses = to_decimal(expense_query["total"])

        # -- 3. PROFIT --
        net_profit = total_revenue - total_expenses

        # -- 4. OUTSTANDING RECEIVABLES --
        # Receivables are pending customer balances
        # Include:
        # - Unpaid reservations (status not checked_out/cancelled): (total_price - advance_paid) + unpaid folios
        # - Unpaid Orders: Order with payment_status != 'paid'
        active_reservations = Reservation.objects.exclude(status__in=["checked_out", "cancelled"])
        
        # Calculate unpaid reservation accommodation fees
        accom_receivables = Decimal("0.00")
        for res in active_reservations:
            res_total = to_decimal(res.total_amount)
            res_adv = to_decimal(res.deposit_amount)
            # Accom receivable is res_total - res_adv
            accom_receivables += max(Decimal("0.00"), res_total - res_adv)

        # Calculate folio charges on active reservations
        folio_receivables_query = FolioCharge.objects.filter(
            reservation__in=active_reservations
        ).aggregate(total=Sum("amount"))
        folio_receivables = to_decimal(folio_receivables_query["total"])

        # Unpaid restaurant/bar orders
        unpaid_orders_query = Order.objects.exclude(
            payment_status="paid"
        ).aggregate(total=Sum("total_amount"))
        unpaid_orders_revenue = to_decimal(unpaid_orders_query["total"])

        total_receivables = accom_receivables + folio_receivables + unpaid_orders_revenue

        # -- 5. REVENUE VS EXPENSE DAILY TREND --
        # Optimized daily grouping using TruncDate
        room_daily = RoomHistory.objects.filter(
            created_at__gte=start_dt, created_at__lt=end_dt
        ).annotate(date=TruncDate("created_at")).values("date").annotate(total=Sum("revenue"))

        fb_daily = Order.objects.filter(
            payment_status="paid",
            updated_at__gte=start_dt, updated_at__lt=end_dt
        ).annotate(date=TruncDate("updated_at")).values("date").annotate(total=Sum("total_amount"))

        folio_daily = FolioCharge.objects.filter(
            added_at__gte=start_dt, added_at__lt=end_dt
        ).annotate(date=TruncDate("added_at")).values("date").annotate(total=Sum("amount"))

        expense_daily = StockTransaction.objects.filter(
            transaction_type="purchase",
            timestamp__gte=start_dt, timestamp__lt=end_dt
        ).annotate(
            date=TruncDate("timestamp"),
            cost=ExpressionWrapper(F("quantity") * F("unit_cost"), output_field=DecimalField(max_digits=12, decimal_places=2))
        ).values("date").annotate(total=Sum("cost"))

        # Map dates to chart points
        trend_map = {}
        curr_day = start_date
        while curr_day <= end_date:
            trend_map[curr_day] = {
                "date": curr_day.isoformat(),
                "revenue": Decimal("0.00"),
                "expense": Decimal("0.00")
            }
            curr_day += timedelta(days=1)

        for item in room_daily:
            day = item["date"]
            if day in trend_map:
                trend_map[day]["revenue"] += to_decimal(item["total"])

        for item in fb_daily:
            day = item["date"]
            if day in trend_map:
                trend_map[day]["revenue"] += to_decimal(item["total"])

        for item in folio_daily:
            day = item["date"]
            if day in trend_map:
                trend_map[day]["revenue"] += to_decimal(item["total"])

        for item in expense_daily:
            day = item["date"]
            if day in trend_map:
                trend_map[day]["expense"] += to_decimal(item["total"])

        # Convert Decimals to float for JSON output
        chart_trend = []
        for day in sorted(trend_map.keys()):
            chart_trend.append({
                "date": trend_map[day]["date"],
                "revenue": float(trend_map[day]["revenue"]),
                "expense": float(trend_map[day]["expense"])
            })

        # -- 6. DETAILED TRANSACTION LOGS (LEDGER) --
        # We query the tables efficiently using select_related
        ledger = []
        
        # Room Histories
        for rh in RoomHistory.objects.filter(
            created_at__gte=start_dt, created_at__lt=end_dt
        ).select_related("room").order_by("-created_at")[:50]:
            ledger.append({
                "id": f"ROOM-{rh.id}",
                "type": "Room Booking",
                "description": f"Room {rh.room.room_number} checkout/checkin ({rh.payment_method})",
                "amount": float(rh.revenue),
                "flow": "in",
                "date": rh.created_at.isoformat(),
            })

        # F&B Paid Orders
        for o in Order.objects.filter(
            payment_status="paid",
            updated_at__gte=start_dt, updated_at__lt=end_dt
        ).select_related("table").order_by("-updated_at")[:50]:
            ledger.append({
                "id": f"FB-{o.id}",
                "type": "F&B Order",
                "description": f"Order #{o.id} - Table {o.table.table_code} ({o.payment_method})",
                "amount": float(o.total_amount),
                "flow": "in",
                "date": o.updated_at.isoformat(),
            })

        # Extra Folio Charges
        for fc in FolioCharge.objects.filter(
            added_at__gte=start_dt, added_at__lt=end_dt
        ).select_related("reservation__room").order_by("-added_at")[:50]:
            ledger.append({
                "id": f"FOLIO-{fc.id}",
                "type": "Extra Charge",
                "description": f"Extra: {fc.description} (Room {fc.reservation.room.room_number})",
                "amount": float(fc.amount),
                "flow": "in",
                "date": fc.added_at.isoformat(),
            })

        # Expenses (Supplier Purchases)
        for st in StockTransaction.objects.filter(
            transaction_type="purchase",
            timestamp__gte=start_dt, timestamp__lt=end_dt
        ).select_related("item", "supplier").order_by("-timestamp")[:50]:
            cost = to_decimal(st.quantity * st.unit_cost)
            ledger.append({
                "id": f"EXP-{st.id}",
                "type": "Supplier Expense",
                "description": f"Purchase: {st.item.name} ({st.quantity} {st.item.unit}) from {st.supplier.name if st.supplier else 'N/A'}",
                "amount": float(cost),
                "flow": "out",
                "date": st.timestamp.isoformat(),
            })

        # Sort the ledger entries chronologically (newest first) and limit to 100 entries
        ledger = sorted(ledger, key=lambda x: x["date"], reverse=True)[:100]

        # Get historical Closed Day Audits (Z-Reports)
        from hotel.models import DayAuditLog
        closed_days = DayAuditLog.objects.filter(
            audit_date__range=(start_date, end_date)
        ).order_by("-audit_date")
        
        closed_days_data = []
        for audit in closed_days:
            closed_days_data.append({
                "date": audit.audit_date.isoformat(),
                "is_closed": audit.is_closed,
                "closed_at": audit.closed_at.isoformat() if audit.closed_at else None,
                "closed_by": audit.closed_by,
                "revenue": float(audit.total_revenue),
                "cash": float(audit.total_cash),
                "telebirr": float(audit.total_telebirr),
                "chapa": float(audit.total_chapa),
                "card": float(audit.total_card),
                "room_revenue": float(audit.total_room_revenue)
            })

        return Response({
            "metrics": {
                "total_revenue": float(total_revenue),
                "room_revenue": float(room_revenue),
                "fb_revenue": float(fb_revenue),
                "folio_revenue": float(folio_revenue),
                "total_expenses": float(total_expenses),
                "net_profit": float(net_profit),
                "total_receivables": float(total_receivables)
            },
            "chart_trend": chart_trend,
            "ledger": ledger,
            "closed_days": closed_days_data
        }, status=status.HTTP_200_OK)


