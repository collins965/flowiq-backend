"""
debts/serializers.py
"""

from decimal import Decimal
from rest_framework import serializers
from .models import Debt


class DebtSerializer(serializers.ModelSerializer):
    amount_paid = serializers.DecimalField(
        max_digits=15, decimal_places=2, read_only=True
    )
    progress_percent = serializers.FloatField(read_only=True)
    is_paid_off = serializers.BooleanField(read_only=True)
    months_to_payoff = serializers.IntegerField(read_only=True, allow_null=True)
    total_interest_cost = serializers.SerializerMethodField()
    avalanche_priority = serializers.SerializerMethodField()

    class Meta:
        model = Debt
        fields = [
            "id",
            "name",
            "lender",
            "type",
            "currency",
            "original_amount",
            "current_balance",
            "amount_paid",
            "progress_percent",
            "interest_rate",
            "monthly_payment",
            "due_date",
            "is_paid_off",
            "months_to_payoff",
            "total_interest_cost",
            "avalanche_priority",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "amount_paid",
            "progress_percent",
            "is_paid_off",
            "months_to_payoff",
            "total_interest_cost",
            "avalanche_priority",
            "created_at",
            "updated_at",
        ]

    def get_total_interest_cost(self, obj) -> Decimal:
        """
        Estimate total interest to be paid over remaining loan life.
        Simple calculation: balance * rate * years remaining.
        """
        if obj.interest_rate <= 0 or obj.monthly_payment <= 0:
            return Decimal("0")
        months = obj.months_to_payoff or 0
        annual_rate = obj.interest_rate / 100
        monthly_rate = annual_rate / 12
        if monthly_rate == 0:
            return Decimal("0")
        total_paid = obj.monthly_payment * months
        return max(Decimal("0"), Decimal(str(total_paid)) - obj.current_balance)

    def get_avalanche_priority(self, obj) -> int:
        """
        Returns the debt's priority rank in the avalanche strategy
        (highest interest rate first). Computed in the list view.
        Placeholder here — overridden in the list view.
        """
        return 0

    def validate_current_balance(self, value):
        if value < 0:
            raise serializers.ValidationError("Current balance cannot be negative.")
        return value

    def validate_original_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Original amount must be greater than zero.")
        return value

    def validate_interest_rate(self, value):
        if value < 0 or value > 1000:
            raise serializers.ValidationError(
                "Interest rate must be between 0 and 1000%."
            )
        return value

    def validate_monthly_payment(self, value):
        if value < 0:
            raise serializers.ValidationError("Monthly payment cannot be negative.")
        return value

    def validate(self, attrs):
        original = attrs.get("original_amount", 0)
        current = attrs.get("current_balance", 0)
        if current > original:
            raise serializers.ValidationError(
                "Current balance cannot exceed the original loan amount."
            )
        return attrs

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)


class DebtSummarySerializer(serializers.Serializer):
    """Debt overview summary for the dashboard."""
    total_debt = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_monthly_payments = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_paid = serializers.DecimalField(max_digits=15, decimal_places=2)
    debt_count = serializers.IntegerField()
    avalanche_order = serializers.ListField()
    snowball_order = serializers.ListField()
    projected_debt_free_months = serializers.IntegerField(allow_null=True)