from django.db import models
from core.models import BaseModel


class SavingsGoal(BaseModel):
    user_id = models.UUIDField()
    name = models.CharField(max_length=255)
    target_amount = models.DecimalField(max_digits=15, decimal_places=2)
    current_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    currency = models.CharField(max_length=10, default="KES")
    target_date = models.DateField(null=True, blank=True)
    category = models.CharField(max_length=255, blank=True)
    is_complete = models.BooleanField(default=False)

    class Meta:
        db_table = "savings_goals"