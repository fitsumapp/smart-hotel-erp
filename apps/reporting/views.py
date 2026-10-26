"""Reporting API views extracted from the legacy facade."""
# Shared imports and compatibility helpers live in users.views during migration.
from users.views import *  # noqa: F401,F403
from django.db import transaction
from core.performance import bounded_date_range, datetime_bounds

class PoliceReportView(APIView):
    """Today's checked-in guests with ID information for police report."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not (request.user.is_superuser or request.user.role in ["admin", "reception", "finance"]):
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
        if not (request.user.is_superuser or request.user.role in ["admin", "reception", "finance"]):
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
    """End-of-day closure report (Z-Report) — supports GET preview and POST closure."""
    permission_classes = [permissions.IsAuthenticated]

    def _get_z_report_payload(self, report_date, user, is_close_action=False):
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

        if is_close_action:
            with transaction.atomic():
                audit, created = DayAuditLog.objects.select_for_update().get_or_create(audit_date=report_date)
                if audit.is_closed and not created:
                    # Day is already finalized — return the stored snapshot unchanged.
                    # Finalized totals must never silently change after closure.
                    closed_at_str = audit.closed_at.isoformat() if audit.closed_at else None
                    closed_by_str = audit.closed_by
                    is_closed_val = True
                    # Return early using the stored financial figures, not the live recalculation.
                    return {
                        "report_type": "Z-Report",
                        "date": report_date.isoformat(),
                        "closed_by": closed_by_str,
                        "closed_at": closed_at_str,
                        "is_closed": True,
                        "already_closed": True,
                        "restaurant": {
                            "cash": float(audit.total_cash),
                            "chapa": float(audit.total_chapa),
                            "telebirr": float(audit.total_telebirr),
                            "card": float(audit.total_card),
                            "total": float(audit.total_cash + audit.total_chapa + audit.total_telebirr + audit.total_card),
                            "order_count": None,  # Not stored in snapshot
                        },
                        "rooms": {
                            "revenue": float(audit.total_room_revenue),
                            "cash": None,
                            "digital": None,
                            "bank_transfer": None,
                            "checkouts": None,
                        },
                        "grand_total": float(audit.total_revenue),
                        "hotel_name": get_system_settings().hotel_name,
                        "tin_number": get_system_settings().tin_number,
                        "printer_paper_size": get_system_settings().printer_paper_size,
                    }
                # First-time closure: record snapshot
                audit.is_closed = True
                audit.closed_at = timezone.now()
                audit.closed_by = user.username
                audit.total_cash = cash_total
                audit.total_chapa = chapa_total
                audit.total_telebirr = telebirr_total
                audit.total_card = card_total
                audit.total_room_revenue = room_revenue
                audit.total_revenue = grand_total
                audit.save()
            closed_at_str = audit.closed_at.isoformat() if audit.closed_at else None
            closed_by_str = audit.closed_by
            is_closed_val = True
        else:
            audit = DayAuditLog.objects.filter(audit_date=report_date).first()
            is_closed_val = audit.is_closed if audit else False
            closed_at_str = audit.closed_at.isoformat() if (audit and audit.closed_at) else None
            closed_by_str = audit.closed_by if audit else None

        report_label = "Z-Report" if is_closed_val else "Z-Report (Preview)"
        return {
            "report_type": report_label,
            "date": report_date.isoformat(),
            "closed_by": closed_by_str,
            "closed_at": closed_at_str,
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
            "is_closed": is_closed_val,
            "hotel_name": get_system_settings().hotel_name,
            "tin_number": get_system_settings().tin_number,
            "printer_paper_size": get_system_settings().printer_paper_size,
        }

    def get(self, request):
        """Preview Z-Report totals without closing the business day or mutating DayAuditLog."""
        if not (request.user.is_superuser or request.user.role in ["admin", "reception", "finance"]):
            return Response({"error": "Access denied."}, status=403)
        date_param = request.query_params.get("date", timezone.now().date().isoformat())
        try:
            report_date = datetime.fromisoformat(date_param).date()
        except Exception:
            report_date = timezone.now().date()
        payload = self._get_z_report_payload(report_date, request.user, is_close_action=False)
        return Response(payload)

    def post(self, request):
        """Explicitly execute end-of-day closure and mark DayAuditLog.is_closed = True."""
        if not (request.user.is_superuser or request.user.role in ["admin", "reception", "finance"]):
            return Response({"error": "Access denied."}, status=403)
        date_param = request.data.get("date", timezone.now().date().isoformat())
        try:
            report_date = datetime.fromisoformat(date_param).date()
        except Exception:
            report_date = timezone.now().date()
        payload = self._get_z_report_payload(report_date, request.user, is_close_action=True)
        return Response(payload)


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
        from django.db.models import Sum, F, ExpressionWrapper, DecimalField, Q
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
        from hotel.models import Account, JournalEntryItem, ExpenseTransaction
        from apps.finance.services import ensure_default_accounts
        ensure_default_accounts()

        # Check for posted General Ledger entries in this date range
        gl_rev_items = JournalEntryItem.objects.filter(
            entry__date__gte=start_date,
            entry__date__lte=end_date,
            account__account_type="revenue",
        )
        has_gl_entries = gl_rev_items.exists()

        if has_gl_entries:
            # Authoritative double-entry General Ledger calculation:
            # Account 4000: Room Revenue (credit-normal; credits=revenue earned, debits=refunds/reversals)
            # Account 4100: F&B Revenue
            # Account 4200: Folio Extras Revenue
            # Net = Credits − Debits. Negative net is intentionally ALLOWED (net refund period).
            #
            # IMPORTANT LIMITATION: has_gl_entries is a period-level binary flag.
            # If GL entries exist for SOME days in the period but not all, operational revenue
            # for the non-GL days will NOT appear in the total. This is by design: once GL is
            # adopted, operational fallback is retired for that period. A partial GL indicates
            # incomplete GL adoption. Administrators should ensure GL entries are posted for all
            # revenue-generating days before relying on the GL path for period totals.
            def _gl_account_net(code, name_fallback):
                agg = JournalEntryItem.objects.filter(
                    entry__date__gte=start_date,
                    entry__date__lte=end_date,
                ).filter(
                    Q(account__code=code) | Q(account__name__iexact=name_fallback)
                ).aggregate(cr=Sum("amount_credit"), dr=Sum("amount_debit"))
                # Do NOT clamp to zero — negative net correctly reflects a net refund period.
                return to_decimal(agg["cr"]) - to_decimal(agg["dr"])

            room_revenue = _gl_account_net("4000", "Room Revenue")
            fb_revenue = _gl_account_net("4100", "F&B Revenue")
            folio_revenue = _gl_account_net("4200", "Folio Extras Revenue")

            total_rev_agg = gl_rev_items.aggregate(cr=Sum("amount_credit"), dr=Sum("amount_debit"))
            # Allow negative total (net-refund period) — do NOT clamp.
            total_revenue = to_decimal(total_rev_agg["cr"]) - to_decimal(total_rev_agg["dr"])
            classified_sum = room_revenue + fb_revenue + folio_revenue
            if total_revenue < classified_sum:
                total_revenue = classified_sum
        else:
            # Operational model calculation with strict deduplication:
            # 1. F&B Revenue: All paid orders
            fb_rev_query = Order.objects.filter(
                payment_status="paid",
                updated_at__gte=start_dt, updated_at__lt=end_dt
            ).aggregate(total=Sum("total_amount"))
            fb_revenue = to_decimal(fb_rev_query["total"])

            # 2. Folio Revenue: Exclude F&B room charges to prevent double-counting with Order
            folio_rev_query = FolioCharge.objects.filter(
                added_at__gte=start_dt, added_at__lt=end_dt
            ).exclude(
                description__startswith="F&B Order #"
            ).aggregate(total=Sum("amount"))
            folio_revenue = to_decimal(folio_rev_query["total"])

            # 3. Room Revenue: Pure accommodation (lodging) revenue from checkin and checkout events.
            #
            # Revenue attribution rules:
            #   a. Non-prepaid CHECKIN: RoomHistory.revenue = base_price × nights (full stay charged at checkin).
            #      These are counted directly via checkin_rev.
            #   b. Non-prepaid CHECKOUT: RoomHistory.revenue = extras_total only (lodging already paid at checkin).
            #      If the same guest's checkin is also in this period, the checkout event adds zero lodging
            #      (to avoid double-counting). If only the checkout falls in this period (multi-period stay),
            #      we reconstruct lodging from base_price × nights using the matched Reservation.
            #   c. Prepaid stays do NOT create a checkin RoomHistory event — checkout event revenue =
            #      extras_total only (or 0 if no extras). We do NOT add lodging again because prepaid
            #      room revenue is captured at booking/payment time (not via RoomHistory).
            #
            # KNOWN LIMITATION: For prepaid stays the lodging portion is NOT captured by RoomHistory at all.
            # It must be captured via the GL (post_journal_entry at checkout with is_prepaid=True).
            # If GL is absent and stays are prepaid, the fallback will undercount room revenue.
            # This is documented and expected behavior in a partially-implemented GL environment.

            checkin_rev = RoomHistory.objects.filter(
                event_type="checkin",
                created_at__gte=start_dt, created_at__lt=end_dt
            ).aggregate(total=Sum("revenue"))["total"] or Decimal("0.00")

            checkout_histories = list(RoomHistory.objects.filter(
                event_type="checkout",
                created_at__gte=start_dt, created_at__lt=end_dt
            ).select_related("room"))

            checkout_lodging_rev = Decimal("0.00")
            for rh in checkout_histories:
                # Look up the reservation matching this checkout event.
                # Filter by room AND guest_name to prevent selecting the wrong reservation
                # when a room has multiple historical reservations with the same checkout date.
                target_checkout_date = rh.check_out_date or rh.created_at.date()
                res = Reservation.objects.filter(
                    room=rh.room,
                    guest_name=rh.guest_name,
                    check_out_date=target_checkout_date,
                ).order_by("-updated_at").first()

                if res:
                    # Check if this stay's checkin event was already counted in this period.
                    already_recorded_at_checkin = RoomHistory.objects.filter(
                        room=rh.room,
                        event_type="checkin",
                        created_at__gte=start_dt, created_at__lt=end_dt,
                        guest_name=rh.guest_name,
                    ).exists()
                    if not already_recorded_at_checkin:
                        # Checkin not in this period — attribute lodging to checkout date.
                        # For non-prepaid: reconstruct from base_price × nights (safe).
                        # For prepaid: rh.revenue = extras_total only; lodging must come from GL.
                        is_prepaid_checkout = (res.payment_status == "paid" and
                                               not RoomHistory.objects.filter(
                                                   room=rh.room, event_type="checkin",
                                                   guest_name=rh.guest_name
                                               ).exists())
                        if is_prepaid_checkout:
                            # Prepaid stay: lodging not in RoomHistory — cannot safely reconstruct
                            # without GL. Skip to avoid double-counting. (See KNOWN LIMITATION above.)
                            pass
                        else:
                            nights = max((res.check_out_date - res.check_in_date).days, 1)
                            room_base = to_decimal(res.room.base_price) * nights
                            checkout_lodging_rev += room_base
                else:
                    # No matching reservation found — use raw RoomHistory.revenue as best effort.
                    # This may include folio extras if the checkout was non-prepaid and combined.
                    # Accept this as an approximation when the reservation record is absent.
                    checkout_lodging_rev += to_decimal(rh.revenue)

            room_revenue = to_decimal(checkin_rev) + to_decimal(checkout_lodging_rev)
            total_revenue = room_revenue + fb_revenue + folio_revenue

        # -- 2. EXPENSE CALCULATIONS --
        # Expenses: inventory purchases (StockTransactions of type 'purchase') + logged ExpenseTransactions
        expense_query = StockTransaction.objects.filter(
            transaction_type="purchase",
            timestamp__gte=start_dt, timestamp__lt=end_dt
        ).annotate(
            cost=ExpressionWrapper(F("quantity") * F("unit_cost"), output_field=DecimalField(max_digits=12, decimal_places=2))
        ).aggregate(total=Sum("cost"))
        stock_purchases = to_decimal(expense_query["total"])

        logged_exp_query = ExpenseTransaction.objects.filter(
            date__gte=start_date, date__lte=end_date
        ).aggregate(total=Sum("amount"))
        logged_expenses = to_decimal(logged_exp_query["total"])

        total_expenses = stock_purchases + logged_expenses

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

        if has_gl_entries:
            gl_daily_rev = JournalEntryItem.objects.filter(
                entry__date__gte=start_date,
                entry__date__lte=end_date,
                account__account_type="revenue",
            ).values("entry__date").annotate(
                cr=Sum("amount_credit"), dr=Sum("amount_debit")
            )
            for item in gl_daily_rev:
                day = item["entry__date"]
                if day in trend_map:
                    # Allow negative net (net-refund day) — do NOT clamp.
                    net_cr = to_decimal(item["cr"]) - to_decimal(item["dr"])
                    trend_map[day]["revenue"] += net_cr
        else:
            checkin_daily = RoomHistory.objects.filter(
                event_type="checkin",
                created_at__gte=start_dt, created_at__lt=end_dt
            ).annotate(date=TruncDate("created_at")).values("date").annotate(total=Sum("revenue"))
            for item in checkin_daily:
                day = item["date"]
                if day in trend_map:
                    trend_map[day]["revenue"] += to_decimal(item["total"])

            # Use the already-evaluated checkout_histories list (computed above) for the chart.
            # Apply the same deduplication logic used for the period total.
            for rh in checkout_histories:
                day = rh.created_at.date()
                if day in trend_map:
                    target_checkout_date = rh.check_out_date or rh.created_at.date()
                    res = Reservation.objects.filter(
                        room=rh.room,
                        guest_name=rh.guest_name,
                        check_out_date=target_checkout_date,
                    ).order_by("-updated_at").first()
                    if res:
                        already_recorded_at_checkin = RoomHistory.objects.filter(
                            room=rh.room,
                            event_type="checkin",
                            created_at__gte=start_dt, created_at__lt=end_dt,
                            guest_name=rh.guest_name,
                        ).exists()
                        if not already_recorded_at_checkin:
                            is_prepaid_checkout = (res.payment_status == "paid" and
                                                   not RoomHistory.objects.filter(
                                                       room=rh.room, event_type="checkin",
                                                       guest_name=rh.guest_name
                                                   ).exists())
                            if not is_prepaid_checkout:
                                nights = max((res.check_out_date - res.check_in_date).days, 1)
                                room_base = to_decimal(res.room.base_price) * nights
                                trend_map[day]["revenue"] += room_base
                    else:
                        trend_map[day]["revenue"] += to_decimal(rh.revenue)

            for item in fb_daily:
                day = item["date"]
                if day in trend_map:
                    trend_map[day]["revenue"] += to_decimal(item["total"])

            folio_daily_dedup = FolioCharge.objects.filter(
                added_at__gte=start_dt, added_at__lt=end_dt
            ).exclude(
                description__startswith="F&B Order #"
            ).annotate(date=TruncDate("added_at")).values("date").annotate(total=Sum("amount"))

            for item in folio_daily_dedup:
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
            tbl_code = o.table.table_code if o.table else "N/A"
            ledger.append({
                "id": f"FB-{o.id}",
                "type": "F&B Order",
                "description": f"Order #{o.id} - Table {tbl_code} ({o.payment_method})",
                "amount": float(o.total_amount),
                "flow": "in",
                "date": o.updated_at.isoformat(),
            })

        # Extra Folio Charges (exclude F&B room charges so they aren't listed twice in the ledger)
        for fc in FolioCharge.objects.filter(
            added_at__gte=start_dt, added_at__lt=end_dt
        ).exclude(
            description__startswith="F&B Order #"
        ).select_related("reservation__room").order_by("-added_at")[:50]:
            room_num = getattr(getattr(fc.reservation, "room", None), "room_number", "N/A")
            ledger.append({
                "id": f"FOLIO-{fc.id}",
                "type": "Extra Charge",
                "description": f"Extra: {fc.description} (Room {room_num})",
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

        # Expenses (Expense Transactions)
        for et in ExpenseTransaction.objects.filter(
            date__gte=start_date, date__lte=end_date
        ).order_by("-date")[:50]:
            ledger.append({
                "id": f"EXPTX-{et.id}",
                "type": "General Expense",
                "description": f"{et.description}",
                "amount": float(et.amount),
                "flow": "out",
                "date": datetime.combine(et.date, datetime.min.time(), tzinfo=timezone.get_current_timezone()).isoformat(),
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


