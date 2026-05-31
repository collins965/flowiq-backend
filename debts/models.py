"""
debts/models.py
"""

from django.db import models
from django.conf import settings
from core.models import BaseModel


class Debt(BaseModel):
    DEBT_TYPES = [
        ("personal_loan", "Personal Loan"),
        ("credit_card", "Credit Card"),
        ("mobile_loan", "Mobile Loan"),
        ("mortgage", "Mortgage"),
        ("sacco", "SACCO Loan"),
        ("business_loan", "Business Loan"),
        ("family_friend", "Family / Friend"),
        ("other", "Other"),
    ]

    # Kenya-specific mobile loan presets
    KENYAN_LENDERS = [
        ("fuliza", "Fuliza"),
        ("m_shwari", "M-Shwari"),
        ("kcb_mpesa", "KCB M-Pesa"),
        ("tala", "Tala"),
        ("branch", "Branch"),
        ("equity_eazzy", "Equity Eazzy Loan"),
        ("other", "Other"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="debts",
    )

    name = models.CharField(max_length=255)
    lender = models.CharField(max_length=255, blank=True, default="")
    type = models.CharField(
        max_length=50,
        choices=DEBT_TYPES,
        default="personal_loan",
    )
    currency = models.CharField(max_length=10, default="KES")

    # Amounts
    original_amount = models.DecimalField(max_digits=15, decimal_places=2)
    current_balance = models.DecimalField(max_digits=15, decimal_places=2)
    interest_rate = models.DecimalField(
        max_digits=8, decimal_places=4, default=0,
        help_text="Annual interest rate as a percentage e.g. 14.5 for 14.5%"
    )
    monthly_payment = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    due_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")

    class Meta:
        db_table = "debts"
        ordering = ["-current_balance"]
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["user", "type"]),
        ]

    def __str__(self):
        return f"{self.name} — {self.currency} {self.current_balance}"

    @property
    def amount_paid(self):
        return max(0, self.original_amount - self.current_balance)

    @property
    def progress_percent(self):
        if self.original_amount <= 0:
            return 0
        return min(100, float(self.amount_paid / self.original_amount * 100))

    @property
    def is_paid_off(self):
        return self.current_balance <= 0

    @property
    def months_to_payoff(self):
        """Estimate months to pay off at current monthly payment rate."""
        if self.monthly_payment <= 0 or self.current_balance <= 0:
            return None
        # Simple estimate without compounding
        return int(self.current_balance / self.monthly_payment)