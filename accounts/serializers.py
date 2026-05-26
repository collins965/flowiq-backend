"""
accounts/serializers.py
"""

from rest_framework import serializers
from .models import Account


class AccountSerializer(serializers.ModelSerializer):
    """Full serializer — used for create, retrieve, update."""

    transaction_count = serializers.SerializerMethodField()

    class Meta:
        model = Account
        fields = [
            "id",
            "name",
            "type",
            "currency",
            "balance",
            "institution_name",
            "is_active",
            "transaction_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "transaction_count"]

    def get_transaction_count(self, obj) -> int:
        """Return how many transactions are linked to this account."""
        return obj.transactions.count()

    def validate_balance(self, value):
        if value < 0:
            raise serializers.ValidationError(
                "Balance cannot be negative. Use a debt record for liabilities."
            )
        return value

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Account name cannot be blank.")
        return value

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)


class AccountListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for list views.
    Skips transaction_count to avoid N+1 queries on large lists.
    """

    class Meta:
        model = Account
        fields = [
            "id",
            "name",
            "type",
            "currency",
            "balance",
            "institution_name",
            "is_active",
            "created_at",
        ]