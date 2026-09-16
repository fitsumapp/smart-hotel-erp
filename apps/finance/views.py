"""Finance API views extracted from the legacy facade."""
# Shared imports and compatibility helpers live in users.views during migration.
from users.views import *  # noqa: F401,F403
from core.performance import bounded_date_range, datetime_bounds
from .selectors import select_accounts, select_journal_entries

class AccountViewSet(viewsets.ModelViewSet):
    serializer_class = AccountSerializer
    permission_classes = [IsFinanceStaff]

    def get_queryset(self):
        ensure_default_accounts()
        return select_accounts(self.request.query_params)

    def create(self, request, *args, **kwargs):
        if request.user.role not in ["admin", "finance"] and not request.user.is_superuser:
            return Response({"error": "Access denied. Only hotel administrators or finance staff can create accounts."}, status=403)
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class JournalEntryViewSet(viewsets.ModelViewSet):
    serializer_class = JournalEntrySerializer
    permission_classes = [IsFinanceStaff]

    http_method_names = ["get", "post", "head", "options"]
    def get_queryset(self):
        return select_journal_entries(self.request.query_params)

    def create(self, request, *args, **kwargs):
        if request.user.role not in ["admin", "finance"] and not request.user.is_superuser:
            return Response({"error": "Access denied."}, status=403)
            
        description = request.data.get("description", "")
        items_data = request.data.get("items", [])
        date_str = request.data.get("date")
        
        entry_date = None
        if date_str:
            try:
                entry_date = datetime.fromisoformat(date_str).date()
            except ValueError:
                pass
                
        try:
            entry = post_journal_entry(description, items_data, entry_date)
            return Response(JournalEntrySerializer(entry).data, status=status.HTTP_201_CREATED)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


    @action(detail=True, methods=["post"])
    def reverse(self, request, pk=None):
        if request.user.role not in ["admin", "finance"] and not request.user.is_superuser:
            return Response({"error": "Access denied."}, status=403)
        reason = str(request.data.get("reason") or "").strip()
        if not reason:
            return Response({"error": "Reversal reason is required."}, status=400)
        try:
            reversal, created = reverse_entry(entry_id=pk, reason=reason)
        except JournalEntry.DoesNotExist:
            return Response({"error": "Journal entry not found."}, status=404)
        except Exception as exc:
            return Response({"error": str(exc)}, status=400)
        return Response(
            {"created": created, "entry": JournalEntrySerializer(reversal).data},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class ExpenseTransactionViewSet(viewsets.ModelViewSet):
    serializer_class = ExpenseTransactionSerializer
    permission_classes = [IsFinanceStaff]

    def get_queryset(self):
        return ExpenseTransaction.objects.all().select_related("expense_account", "payment_account", "supplier")

    def create(self, request, *args, **kwargs):
        if request.user.role not in ["admin", "finance"] and not request.user.is_superuser:
            return Response({"error": "Access denied."}, status=403)
            
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        expense = serializer.save()
        
        # Post the automatic double-entry JV for the expense!
        # Debit Expense Account, Credit Cash/Bank (Payment Account)
        try:
            jv_items = [
                {
                    "account_code": expense.expense_account.code,
                    "debit": expense.amount,
                    "credit": Decimal("0.00")
                },
                {
                    "account_code": expense.payment_account.code,
                    "debit": Decimal("0.00"),
                    "credit": expense.amount
                }
            ]
            post_journal_entry(
                description=f"Auto JV: Expense - {expense.description}",
                items=jv_items,
                date=expense.date
            )
        except Exception as e:
            # Rollback and return error
            expense.delete()
            logger.exception("Expense journal posting failed")
            return Response({"error": "Unable to post expense journal."}, status=status.HTTP_400_BAD_REQUEST)
            
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class BudgetViewSet(viewsets.ModelViewSet):
    serializer_class = BudgetSerializer
    permission_classes = [IsFinanceStaff]

    def get_queryset(self):
        return Budget.objects.all().select_related("account")

    def create(self, request, *args, **kwargs):
        if request.user.role not in ["admin", "finance"] and not request.user.is_superuser:
            return Response({"error": "Access denied."}, status=403)
            
        account_id = request.data.get("account")
        amount = request.data.get("amount")
        year = request.data.get("year")
        month = request.data.get("month")
        
        try:
            account = Account.objects.get(id=account_id)
        except Account.DoesNotExist:
            return Response({"error": "Account not found."}, status=status.HTTP_400_BAD_REQUEST)
            
        budget, created = Budget.objects.update_or_create(
            account=account,
            year=year,
            month=month,
            defaults={"amount": Decimal(str(amount))}
        )
        return Response(BudgetSerializer(budget).data, status=status.HTTP_200_OK if not created else status.HTTP_201_CREATED)


class FinancialStatementsView(APIView):
    permission_classes = [IsFinanceStaff]

    def get(self, request):
        if request.user.role not in ["admin", "finance"] and not request.user.is_superuser:
            return Response({"error": "Access denied."}, status=403)
            
        ensure_default_accounts()
        accounts = Account.objects.all()
        
        # 1. Income Statement (P&L)
        revenue_accounts = []
        expense_accounts = []
        total_revenue = Decimal("0.00")
        total_expenses = Decimal("0.00")
        
        for acct in accounts:
            bal = acct.cached_balance
            if acct.account_type == "revenue":
                revenue_accounts.append({
                    "code": acct.code,
                    "name": acct.name,
                    "balance": float(bal)
                })
                total_revenue += bal
            elif acct.account_type == "expense":
                expense_accounts.append({
                    "code": acct.code,
                    "name": acct.name,
                    "balance": float(bal)
                })
                total_expenses += bal
                
        net_income = total_revenue - total_expenses
        
        # 2. Balance Sheet
        asset_accounts = []
        liability_accounts = []
        equity_accounts = []
        total_assets = Decimal("0.00")
        total_liabilities = Decimal("0.00")
        total_equity = Decimal("0.00")
        
        for acct in accounts:
            bal = acct.cached_balance
            if acct.account_type == "asset":
                asset_accounts.append({
                    "code": acct.code,
                    "name": acct.name,
                    "balance": float(bal)
                })
                total_assets += bal
            elif acct.account_type == "liability":
                liability_accounts.append({
                    "code": acct.code,
                    "name": acct.name,
                    "balance": float(bal)
                })
                total_liabilities += bal
            elif acct.account_type == "equity":
                # Retained earnings includes Net Income from P&L
                if acct.code == "3000":
                    retained_bal = bal + net_income
                    equity_accounts.append({
                        "code": acct.code,
                        "name": acct.name,
                        "balance": float(retained_bal)
                    })
                    total_equity += retained_bal
                else:
                    equity_accounts.append({
                        "code": acct.code,
                        "name": acct.name,
                        "balance": float(bal)
                    })
                    total_equity += bal
                    
        return Response({
            "income_statement": {
                "revenue": revenue_accounts,
                "expenses": expense_accounts,
                "total_revenue": float(total_revenue),
                "total_expenses": float(total_expenses),
                "net_income": float(net_income)
            },
            "balance_sheet": {
                "assets": asset_accounts,
                "liabilities": liability_accounts,
                "equity": equity_accounts,
                "total_assets": float(total_assets),
                "total_liabilities": float(total_liabilities),
                "total_equity": float(total_equity)
            }
        })


class TaxReportView(APIView):
    permission_classes = [IsFinanceStaff]

    def get(self, request):
        if request.user.role not in ["admin", "finance"] and not request.user.is_superuser:
            return Response({"error": "Access denied."}, status=403)
            
        today = timezone.now().date()
        default_start = today.replace(day=1)
        
        start_date_str = request.query_params.get("start_date")
        end_date_str = request.query_params.get("end_date")
        
        try:
            start_date = datetime.fromisoformat(start_date_str).date() if start_date_str else default_start
        except ValueError:
            start_date = default_start
        try:
            end_date = datetime.fromisoformat(end_date_str).date() if end_date_str else today
        except ValueError:
            end_date = today
            
        # VAT and Service Charge are collected on:
        # 1. Restaurant Orders
        from django.db.models import Sum
        order_taxes = Order.objects.filter(
            payment_status="paid",
            updated_at__gte=start_dt, updated_at__lt=end_dt
        ).aggregate(
            vat=Sum("vat_amount"),
            service_charge=Sum("service_charge_amount"),
            subtotal=Sum("sub_total"),
            total=Sum("total_amount")
        )
        
        # 2. Rooms (Bookings - SystemSettings tax ratios on room histories or reservations)
        room_rev = RoomHistory.objects.filter(
            created_at__gte=start_dt, created_at__lt=end_dt
        ).aggregate(total=Sum("revenue"))["total"] or Decimal("0.00")
        
        settings_obj = get_system_settings()
        room_subtotal = Decimal("0.00")
        room_vat = Decimal("0.00")
        room_sc = Decimal("0.00")
        
        if room_rev > 0:
            vat_pct = to_decimal(settings_obj.vat_percentage) if settings_obj.vat_enabled else Decimal("0")
            sc_pct = to_decimal(settings_obj.service_charge_percentage) if settings_obj.service_charge_enabled else Decimal("0")
            
            divider = Decimal("1.0") + (vat_pct + sc_pct) / Decimal("100")
            room_subtotal = (room_rev / divider).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
            
            if settings_obj.vat_enabled:
                room_vat = (room_subtotal * vat_pct / Decimal("100")).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
            if settings_obj.service_charge_enabled:
                room_sc = (room_subtotal * sc_pct / Decimal("100")).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
                
        fb_subtotal = to_decimal(order_taxes["subtotal"])
        fb_vat = to_decimal(order_taxes["vat"])
        fb_sc = to_decimal(order_taxes["service_charge"])
        fb_total = to_decimal(order_taxes["total"])
        
        return Response({
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "restaurant": {
                "subtotal": float(fb_subtotal),
                "vat": float(fb_vat),
                "service_charge": float(fb_sc),
                "total": float(fb_total)
            },
            "rooms": {
                "subtotal": float(room_subtotal),
                "vat": float(room_vat),
                "service_charge": float(room_sc),
                "total": float(room_rev)
            },
            "aggregated": {
                "vat_collected": float(fb_vat + room_vat),
                "service_charge_collected": float(fb_sc + room_sc),
                "total_tax_collected": float(fb_vat + room_vat + fb_sc + room_sc)
            }
        })


class PayrollEntryViewSet(viewsets.ModelViewSet):
    """
    Full CRUD for PayrollEntry.
    Supports filtering by department, status, year, month.
    Automatically posts a GL journal entry when status is set to 'paid'.
    """
    serializer_class = PayrollEntrySerializer
    permission_classes = [IsFinanceStaff]

    def get_queryset(self):
        if self.request.user.role not in ['admin', 'finance'] and not self.request.user.is_superuser:
            return PayrollEntry.objects.none()

        qs = PayrollEntry.objects.all()

        dept   = self.request.query_params.get('department')
        st     = self.request.query_params.get('status')
        year   = self.request.query_params.get('year')
        month  = self.request.query_params.get('month')

        if dept:  qs = qs.filter(department=dept)
        if st:    qs = qs.filter(status=st)
        if year:  qs = qs.filter(pay_period_end__year=year)
        if month: qs = qs.filter(pay_period_end__month=month)

        return qs

    def perform_create(self, serializer):
        entry = serializer.save()
        if entry.status == 'paid':
            self._post_payroll_gl(entry)

    def perform_update(self, serializer):
        old_status = self.get_object().status
        entry = serializer.save()
        if old_status != 'paid' and entry.status == 'paid':
            self._post_payroll_gl(entry)

    def _post_payroll_gl(self, entry):
        """Dr: Salary Expense  Cr: Cash (net pay) + Tax/Pension Payable (deductions)"""
        ensure_default_accounts()
        try:
            salary_exp   = Account.objects.get(code='5000')
            cash_account = Account.objects.get(code='1000')

            gross   = to_decimal(entry.gross_pay)
            net_pay = to_decimal(entry.net_pay)
            deductions = gross - net_pay

            items = [
                {'account': salary_exp,   'debit': gross,      'credit': Decimal('0')},
                {'account': cash_account, 'debit': Decimal('0'), 'credit': net_pay},
            ]

            # If there are deductions, credit a Liability account (Tax Payable / 2100)
            if deductions > 0:
                try:
                    tax_payable = Account.objects.get(code='2100')
                except Account.DoesNotExist:
                    tax_payable = Account.objects.filter(account_type='liability').first()
                if tax_payable:
                    items.append({'account': tax_payable, 'debit': Decimal('0'), 'credit': deductions})

            post_journal_entry(
                description=(
                    f"Payroll — {entry.employee_name} ({entry.department}) "
                    f"{entry.pay_period_start} to {entry.pay_period_end}"
                ),
                items=items,
                date=entry.payment_date or entry.pay_period_end,
            )
        except Account.DoesNotExist:
            pass


class PayrollSummaryView(APIView):
    """Payroll KPIs and department breakdown for a given month/year."""
    permission_classes = [IsFinanceStaff]

    def get(self, request):
        if request.user.role not in ['admin', 'finance'] and not request.user.is_superuser:
            return Response({'error': 'Access denied.'}, status=403)

        from django.db.models import Sum, Count

        year  = int(request.query_params.get('year',  timezone.now().year))
        month = int(request.query_params.get('month', timezone.now().month))

        qs = PayrollEntry.objects.filter(
            pay_period_end__year=year,
            pay_period_end__month=month,
        )

        totals = qs.aggregate(
            total_gross=Sum('gross_pay'),
            total_net=Sum('net_pay'),
            total_tax=Sum('income_tax'),
            total_pension_emp=Sum('pension_employee'),
            total_pension_er=Sum('pension_employer'),
            total_bonus=Sum('bonus'),
            total_overtime=Sum('overtime_pay'),
            total_allowances=Sum('allowances'),
            headcount=Count('id'),
        )

        department_labels = dict(PayrollEntry.DEPARTMENT_CHOICES)
        department_rows = qs.values("department").annotate(
            gross=Sum("gross_pay"), net=Sum("net_pay"), count=Count("id")
        ).order_by("department")
        dept_data = [
            {
                "department": department_labels.get(row["department"], row["department"]),
                "code": row["department"],
                "headcount": row["count"] or 0,
                "total_gross": float(row["gross"] or 0),
                "total_net": float(row["net"] or 0),
            }
            for row in department_rows
        ]

        return Response({
            'year': year,
            'month': month,
            'summary': {
                'headcount':                totals['headcount'] or 0,
                'total_gross':              float(totals['total_gross'] or 0),
                'total_net':                float(totals['total_net'] or 0),
                'total_tax':                float(totals['total_tax'] or 0),
                'total_pension_employee':   float(totals['total_pension_emp'] or 0),
                'total_pension_employer':   float(totals['total_pension_er'] or 0),
                'total_bonus':              float(totals['total_bonus'] or 0),
                'total_overtime':           float(totals['total_overtime'] or 0),
                'total_allowances':         float(totals['total_allowances'] or 0),
            },
            'by_department': dept_data,
        })


