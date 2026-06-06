"""
investments/models.py
"""

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from core.models import BaseModel


class InvestmentType(models.TextChoices):
    STOCK = "stock", "Stock"
    CRYPTO = "crypto", "Cryptocurrency"
    BOND = "bond", "Bond"
    REAL_ESTATE = "real_estate", "Real Estate"
    MONEY_MARKET = "money_market", "Money Market Fund"
    SACCO = "sacco", "SACCO"
    TREASURY = "treasury", "Treasury Bill / Bond"
    ETF = "etf", "ETF"
    OTHER = "other", "Other"


class Investment(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="investments",
    )

    name = models.CharField(max_length=255)
    investment_type = models.CharField(
        max_length=50,
        choices=InvestmentType.choices,
        default=InvestmentType.OTHER,
    )
    amount_invested = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    current_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    currency = models.CharField(max_length=3, default="KES")
    start_date = models.DateField(null=True, blank=True)
    institution = models.CharField(
        max_length=255, blank=True, default="",
        help_text="e.g. Cytonn, CIC, NSE, Binance"
    )
    notes = models.TextField(blank=True, default="")

    class Meta:
        db_table = "investments"
        ordering = ["-current_value"]
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["user", "investment_type"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.user})"

    @property
    def gain_loss(self):
        return self.current_value - self.amount_invested

    @property
    def return_percent(self):
        if self.amount_invested <= 0:
            return 0
        return float(self.gain_loss / self.amount_invested * 100)

    @property
    def is_profit(self):
        return self.current_value >= self.amount_invested