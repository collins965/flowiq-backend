"""
investments/serializers.py
"""

from decimal import Decimal
from rest_framework import serializers
from .models import Investment, InvestmentType


class InvestmentSerializer(serializers.ModelSerializer):
    gain_loss = serializers.DecimalField(
        max_digits=15, decimal_places=2, read_only=True
    )
    return_percent = serializers.FloatField(read_only=True)
    is_profit = serializers.BooleanField(read_only=True)
    investment_type_display = serializers.CharField(
        source="get_investment_type_display", read_only=True
    )

    class Meta:
        model = Investment
        fields = [
            "id",
            "name",
            "investment_type",
            "investment_type_display",
            "amount_invested",
            "current_value",
            "gain_loss",
            "return_percent",
            "is_profit",
            "currency",
            "start_date",
            "institution",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "gain_loss",
            "return_percent",
            "is_profit",
            "investment_type_display",
            "created_at",
            "updated_at",
        ]

    def validate_amount_invested(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Amount invested must be greater than zero."
            )
        return value

    def validate_current_value(self, value):
        if value < 0:
            raise serializers.ValidationError(
                "Current value cannot be negative."
            )
        return value

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)