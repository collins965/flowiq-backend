"""
savings/models.py
"""

from django.db import models
from django.conf import settings
from core.models import BaseModel


class SavingsGoal(BaseModel):
    CATEGORY_CHOICES = [
        ("emergency", "Emergency Fund"),
        ("travel", "Travel"),
        ("education", "Education"),
        ("business", "Business"),
        ("asset", "Asset Purchase"),
        ("retirement", "Retirement"),
        ("other", "Other"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="savings_goals",
    )

    name = models.CharField(max_length=255)
    target_amount = models.DecimalField(max_digits=15, decimal_places=2)
    current_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    currency = models.CharField(max_length=10, default="KES")
    target_date = models.DateField(null=True, blank=True)
    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        default="other",
    )
    is_complete = models.BooleanField(default=False)
    ai_coaching_message = models.TextField(blank=True, default="")
    notes = models.TextField(blank=True, default="")

    class Meta:
        db_table = "savings_goals"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["user", "is_complete"]),
        ]

    def __str__(self):
        return f"{self.name} — {self.currency} {self.current_amount}/{self.target_amount}"

    @property
    def progress_percent(self):
        if self.target_amount <= 0:
            return 0
        return min(100, float(self.current_amount / self.target_amount * 100))

    @property
    def amount_remaining(self):
        return max(0, self.target_amount - self.current_amount)

    @property
    def is_on_track(self):
        """Check if current savings rate will hit target by target_date."""
        from datetime import date
        if not self.target_date or self.is_complete:
            return None
        days_left = (self.target_date - date.today()).days
        if days_left <= 0:
            return self.is_complete
        return self.current_amount >= (
            self.target_amount * (1 - days_left / max(1, (
                self.target_date - self.created_at.date()
            ).days))
        )


class GoalContribution(BaseModel):
    """
    Tracks individual contributions to a savings goal.
    Lets users see their contribution history per goal.
    """
    goal = models.ForeignKey(
        SavingsGoal,
        on_delete=models.CASCADE,
        related_name="contributions",
    )
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    note = models.TextField(blank=True, default="")

    class Meta:
        db_table = "goal_contributions"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.goal.name} +{self.amount}"