"""
budgets/serializers.py
"""

from decimal import Decimal
from datetime import date

from rest_framework import serializers

from .models import Budget
from transactions.models import Category


class BudgetSerializer(serializers.ModelSerializer):
    """Full serializer — used for create, retrieve, update."""

    category_name = serializers.CharField(source="category.name", read_only=True)
    category_icon = serializers.CharField(source="category.icon", read_only=True)
    category_color = serializers.CharField(source="category.color", read_only=True)

    # Computed fields — injected by the view
    amount_spent = serializers.DecimalField(
        max_digits=15, decimal_places=2, read_only=True, default=0
    )
    amount_remaining = serializers.DecimalField(
        max_digits=15, decimal_places=2, read_only=True, default=0
    )
    percent_used = serializers.FloatField(read_only=True, default=0)
    is_over_budget = serializers.BooleanField(read_only=True, default=False)
    projected_spend = serializers.DecimalField(
        max_digits=15, decimal_places=2, read_only=True, default=0
    )

    class Meta:
        model = Budget
        fields = [
            "id",
            "category",
            "category_name",
            "category_icon",
            "category_color",
            "amount",
            "period",
            "note",
            "start_date",
            "amount_spent",
            "amount_remaining",
            "percent_used",
            "is_over_budget",
            "projected_spend",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "amount_spent",
            "amount_remaining",
            "percent_used",
            "is_over_budget",
            "projected_spend",
        ]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Budget amount must be greater than zero.")
        return value

    def validate_category(self, value):
        request = self.context.get("request")
        if request and not value.is_system and value.user != request.user:
            raise serializers.ValidationError(
                "You can only create budgets for your own categories."
            )
        return value

    def validate_start_date(self, value):
        if value > date.today():
            raise serializers.ValidationError(
                "Start date cannot be in the future."
            )
        return value

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)


class BudgetHealthSerializer(serializers.Serializer):
    score = serializers.IntegerField()
    label = serializers.CharField()
    color = serializers.CharField()
    total_budgeted = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_spent = serializers.DecimalField(max_digits=15, decimal_places=2)
    categories_over_budget = serializers.IntegerField()
    categories_at_risk = serializers.IntegerField()
    categories_on_track = serializers.IntegerField()
    ai_summary = serializers.CharField()