"""
transactions/serializers.py
"""

from rest_framework import serializers

# Account is in the accounts app — not transactions
from accounts.models import Account
from .models import Category, Transaction, ImportHistory


class AccountSerializer(serializers.ModelSerializer):
    """
    Included here for convenience so transaction-related views
    can serialize account data without importing from accounts app directly.
    """
    class Meta:
        model = Account
        fields = [
            "id", "name", "type", "currency",
            "balance", "institution_name", "is_active", "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = [
            "id", "name", "icon", "color",
            "type", "is_system", "parent",
        ]
        read_only_fields = ["id", "is_system"]

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)


class TransactionSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(
        source="category.name", read_only=True
    )
    category_color = serializers.CharField(
        source="category.color", read_only=True
    )
    category_icon = serializers.CharField(
        source="category.icon", read_only=True
    )
    account_name = serializers.CharField(
        source="account.name", read_only=True
    )
    signed_amount = serializers.DecimalField(
        max_digits=15, decimal_places=2, read_only=True
    )

    class Meta:
        model = Transaction
        fields = [
            "id", "date", "amount", "signed_amount",
            "currency", "amount_base_currency",
            "description", "merchant", "type", "source",
            "category", "category_name", "category_color", "category_icon",
            "account", "account_name",
            "fraud_status", "fraud_score",
            "is_duplicate", "notes", "receipt_url",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "source", "fraud_status", "fraud_score",
            "is_duplicate", "created_at", "updated_at",
            "signed_amount",
        ]

    def validate_amount(self, value):
        if value == 0:
            raise serializers.ValidationError("Amount cannot be zero.")
        return value

    def validate(self, attrs):
        # Auto-set amount_base_currency if not provided
        # Exchange rate conversion will be added later
        if "amount_base_currency" not in attrs:
            attrs["amount_base_currency"] = attrs.get("amount", 0)
        return attrs

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        validated_data["source"] = "manual"
        return super().create(validated_data)


class TransactionListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for list views — fewer fields, faster responses.
    """
    category_name = serializers.CharField(
        source="category.name", read_only=True
    )
    category_color = serializers.CharField(
        source="category.color", read_only=True
    )
    category_icon = serializers.CharField(
        source="category.icon", read_only=True
    )

    class Meta:
        model = Transaction
        fields = [
            "id", "date", "amount", "currency",
            "merchant", "description", "type",
            "category", "category_name", "category_color", "category_icon",
            "fraud_status", "is_duplicate",
        ]


class SummarySerializer(serializers.Serializer):
    """
    Dashboard KPI summary — not tied to a model.
    """
    total_income = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_expenses = serializers.DecimalField(max_digits=15, decimal_places=2)
    net_cashflow = serializers.DecimalField(max_digits=15, decimal_places=2)
    transaction_count = serializers.IntegerField()
    top_categories = serializers.ListField()
    period = serializers.CharField()


class ImportHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportHistory
        fields = [
            "id", "filename", "file_format", "source_bank",
            "transaction_count", "duplicates_removed",
            "date_range_start", "date_range_end",
            "status", "error_message", "ai_summary", "created_at",
        ]
        read_only_fields = fields