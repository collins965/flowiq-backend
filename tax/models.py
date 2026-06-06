"""
tax/models.py
"""

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from core.models import BaseModel


class EmploymentType(models.TextChoices):
    EMPLOYED = "employed", "Employed"
    SELF_EMPLOYED = "self_employed", "Self Employed"
    BOTH = "both", "Both"


class TaxSettings(BaseModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tax_settings",
    )
    country = models.CharField(max_length=100, default="Kenya")
    country_code = models.CharField(max_length=3, default="KE")
    region = models.CharField(max_length=100, blank=True, default="")
    employment_type = models.CharField(
        max_length=20,
        choices=EmploymentType.choices,
        default=EmploymentType.EMPLOYED,
    )
    tax_year = models.PositiveIntegerField(null=True, blank=True)

    # Primary employment income
    gross_salary = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        validators=[MinValueValidator(0)],
    )

    # Side hustle / business income
    side_hustle_income = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        validators=[MinValueValidator(0)],
    )

    # Additional income sources stored as JSON
    # Format: [{"type": "freelance", "label": "Upwork", "monthly_amount": 15000}]
    income_sources = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "tax_settings"

    def __str__(self):
        return f"{self.user} — Tax Settings ({self.country})"

    @property
    def total_monthly_income(self):
        from decimal import Decimal
        base = self.gross_salary + self.side_hustle_income
        extra = sum(
            Decimal(str(s.get("monthly_amount", 0)))
            for s in (self.income_sources or [])
        )
        return base + extra


class TaxCalculation(BaseModel):
    """
    Stores the result of each tax calculation run.
    Allows users to view their calculation history.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tax_calculations",
    )
    country_code = models.CharField(max_length=3, default="KE")
    employment_type = models.CharField(max_length=20)
    tax_year = models.PositiveIntegerField()
    gross_monthly_income = models.DecimalField(max_digits=15, decimal_places=2)

    # Full breakdown stored as JSON
    breakdown = models.JSONField(default=dict)

    # Key figures
    net_paye = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    nhif = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    nssf = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    housing_levy = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    net_pay = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    effective_tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    class Meta:
        db_table = "tax_calculations"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.user} — {self.country_code} Tax {self.tax_year}"