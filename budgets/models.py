"""
budgets/models.py
"""

from django.db import models
from django.conf import settings
from core.models import BaseModel


class Budget(BaseModel):
    PERIOD_CHOICES = [
        ("monthly", "Monthly"),
        ("weekly", "Weekly"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="budgets",
    )

    # Link to Category in transactions app
    category = models.ForeignKey(
        "transactions.Category",
        on_delete=models.CASCADE,
        related_name="budgets",
    )

    amount = models.DecimalField(max_digits=15, decimal_places=2)
    period = models.CharField(
        max_length=20,
        choices=PERIOD_CHOICES,
        default="monthly",
    )
    note = models.TextField(blank=True, default="")
    start_date = models.DateField()

    class Meta:
        db_table = "budgets"
        ordering = ["category__name"]
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["user", "category"]),
        ]
        # One budget per category per user
        constraints = [
            models.UniqueConstraint(
                fields=["user", "category"],
                name="unique_user_category_budget",
            )
        ]

    def __str__(self):
        return f"{self.category.name} — {self.amount}/{self.period} ({self.user})"