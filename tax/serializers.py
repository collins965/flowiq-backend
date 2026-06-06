"""
tax/serializers.py
"""

from rest_framework import serializers
from .models import TaxSettings, TaxCalculation, EmploymentType


class TaxSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxSettings
        fields = [
            "id",
            "country",
            "country_code",
            "region",
            "employment_type",
            "tax_year",
            "gross_salary",
            "side_hustle_income",
            "income_sources",
            "total_monthly_income",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "total_monthly_income", "created_at", "updated_at"]

    def validate_gross_salary(self, value):
        if value < 0:
            raise serializers.ValidationError("Gross salary cannot be negative.")
        return value

    def validate_side_hustle_income(self, value):
        if value < 0:
            raise serializers.ValidationError("Side hustle income cannot be negative.")
        return value

    def validate_income_sources(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("income_sources must be a list.")
        for source in value:
            if not isinstance(source, dict):
                raise serializers.ValidationError("Each income source must be an object.")
            if "monthly_amount" not in source:
                raise serializers.ValidationError(
                    "Each income source must have a 'monthly_amount' field."
                )
        return value


class TaxCalculateSerializer(serializers.Serializer):
    """Input serializer for the calculate endpoint."""
    employment_type = serializers.ChoiceField(choices=EmploymentType.choices)
    gross_monthly_salary = serializers.DecimalField(
        max_digits=15, decimal_places=2, required=False, default=0,
        min_value=0,
    )
    annual_business_revenue = serializers.DecimalField(
        max_digits=15, decimal_places=2, required=False, default=0,
        min_value=0,
    )
    country_code = serializers.CharField(max_length=3, default="KE")
    tax_year = serializers.IntegerField(required=False, default=2024)

    def validate(self, attrs):
        emp_type = attrs.get("employment_type")
        salary = attrs.get("gross_monthly_salary", 0)
        revenue = attrs.get("annual_business_revenue", 0)

        if emp_type == "employed" and salary <= 0:
            raise serializers.ValidationError(
                "Gross monthly salary is required for employed individuals."
            )
        if emp_type == "self_employed" and revenue <= 0:
            raise serializers.ValidationError(
                "Annual business revenue is required for self-employed individuals."
            )
        if emp_type == "both" and salary <= 0 and revenue <= 0:
            raise serializers.ValidationError(
                "At least one income source is required."
            )
        return attrs


class TaxCalculationHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxCalculation
        fields = [
            "id",
            "country_code",
            "employment_type",
            "tax_year",
            "gross_monthly_income",
            "net_paye",
            "nhif",
            "nssf",
            "housing_levy",
            "net_pay",
            "effective_tax_rate",
            "breakdown",
            "created_at",
        ]
        read_only_fields = fields