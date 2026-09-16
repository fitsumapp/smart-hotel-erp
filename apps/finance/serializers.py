"""Finance serializers."""
from users.serializers import *  # noqa: F401,F403

class AccountSerializer(serializers.ModelSerializer):
    # Reads from the pre-computed cached_balance column — O(1), no extra DB queries.
    # The JSON key stays "current_balance" so the React frontend needs no changes.
    current_balance = serializers.DecimalField(
        source="cached_balance",
        max_digits=14,
        decimal_places=2,
        read_only=True,
    )

    class Meta:
        model = Account
        fields = ["id", "code", "name", "account_type", "current_balance", "created_at"]


class JournalEntryItemSerializer(serializers.ModelSerializer):
    account_code = serializers.ReadOnlyField(source="account.code")
    account_name = serializers.ReadOnlyField(source="account.name")
    account_type = serializers.ReadOnlyField(source="account.account_type")

    class Meta:
        model = JournalEntryItem
        fields = [
            "id", "entry", "account", "account_code", "account_name", 
            "account_type", "amount_debit", "amount_credit"
        ]


class JournalEntrySerializer(serializers.ModelSerializer):
    items = JournalEntryItemSerializer(many=True, read_only=True)

    class Meta:
        model = JournalEntry
        fields = ["id", "entry_number", "date", "description", "items", "created_at"]


class ExpenseTransactionSerializer(serializers.ModelSerializer):
    expense_account_name = serializers.ReadOnlyField(source="expense_account.name")
    expense_account_code = serializers.ReadOnlyField(source="expense_account.code")
    payment_account_name = serializers.ReadOnlyField(source="payment_account.name")
    payment_account_code = serializers.ReadOnlyField(source="payment_account.code")
    supplier_name = serializers.ReadOnlyField(source="supplier.name")

    class Meta:
        model = ExpenseTransaction
        fields = [
            "id", "description", "amount", "date", 
            "expense_account", "expense_account_code", "expense_account_name",
            "payment_account", "payment_account_code", "payment_account_name",
            "supplier", "supplier_name", "reference_number", "created_at"
        ]


class BudgetSerializer(serializers.ModelSerializer):
    account_code = serializers.ReadOnlyField(source="account.code")
    account_name = serializers.ReadOnlyField(source="account.name")
    account_type = serializers.ReadOnlyField(source="account.account_type")

    class Meta:
        model = Budget
        fields = [
            "id", "account", "account_code", "account_name",
            "account_type", "amount", "year", "month", "created_at"
        ]


class PayrollEntrySerializer(serializers.ModelSerializer):
    total_deductions = serializers.SerializerMethodField()
    employer_cost    = serializers.SerializerMethodField()

    class Meta:
        model = PayrollEntry
        fields = [
            "id", "employee_name", "employee_id", "department", "position",
            "pay_period_start", "pay_period_end", "payment_date",
            "basic_salary", "overtime_pay", "bonus", "allowances",
            "income_tax", "pension_employee", "pension_employer", "other_deductions",
            "gross_pay", "net_pay",
            "total_deductions", "employer_cost",
            "status", "notes", "created_at", "updated_at",
        ]
        read_only_fields = ["gross_pay", "net_pay", "created_at", "updated_at"]

    def get_total_deductions(self, obj):
        from decimal import Decimal
        return float(
            Decimal(str(obj.income_tax)) +
            Decimal(str(obj.pension_employee)) +
            Decimal(str(obj.other_deductions))
        )

    def get_employer_cost(self, obj):
        from decimal import Decimal
        return float(Decimal(str(obj.gross_pay)) + Decimal(str(obj.pension_employer)))


