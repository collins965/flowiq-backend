"""
savings/serializers.py
"""

from decimal import Decimal
from datetime import date

from rest_framework import serializers
from .models import SavingsGoal, GoalContribution


class GoalContributionSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoalContribution
        fields = ["id", "amount", "note", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Contribution amount must be greater than zero.")
        return value


class SavingsGoalSerializer(serializers.ModelSerializer):
    progress_percent = serializers.FloatField(read_only=True)
    amount_remaining = serializers.DecimalField(
        max_digits=15, decimal_places=2, read_only=True
    )
    is_on_track = serializers.BooleanField(read_only=True)
    days_remaining = serializers.SerializerMethodField()
    monthly_needed = serializers.SerializerMethodField()
    recent_contributions = GoalContributionSerializer(
        source="contributions", many=True, read_only=True
    )

    class Meta:
        model = SavingsGoal
        fields = [
            "id",
            "name",
            "target_amount",
            "current_amount",
            "amount_remaining",
            "progress_percent",
            "currency",
            "target_date",
            "category",
            "is_complete",
            "is_on_track",
            "days_remaining",
            "monthly_needed",
            "ai_coaching_message",
            "notes",
            "recent_contributions",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "is_complete",
            "progress_percent",
            "amount_remaining",
            "is_on_track",
            "days_remaining",
            "monthly_needed",
            "ai_coaching_message",
            "created_at",
            "updated_at",
        ]

    def get_days_remaining(self, obj) -> int | None:
        if not obj.target_date:
            return None
        delta = (obj.target_date - date.today()).days
        return max(0, delta)

    def get_monthly_needed(self, obj) -> Decimal | None:
        """How much needs to be saved per month to hit the target."""
        if not obj.target_date:
            return None
        days_left = (obj.target_date - date.today()).days
        if days_left <= 0:
            return obj.amount_remaining
        months_left = max(1, days_left / 30)
        return round(obj.amount_remaining / Decimal(str(months_left)), 2)

    def validate_target_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Target amount must be greater than zero.")
        return value

    def validate_target_date(self, value):
        if value and value <= date.today():
            raise serializers.ValidationError("Target date must be in the future.")
        return value

    def validate_current_amount(self, value):
        if value < 0:
            raise serializers.ValidationError("Current amount cannot be negative.")
        return value

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)