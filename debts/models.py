from django.db import models
from core.models import BaseModel


class Debt(BaseModel):
    user_id = models.UUIDField()
    name = models.CharField(max_length=255)
    lender = models.CharField(max_length=255, blank=True)
    original_amount = models.DecimalField(max_digits=15, decimal_places=2)
    current_balance = models.DecimalField(max_digits=15, decimal_places=2)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    monthly_payment = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    due_date = models.DateField(null=True, blank=True)
    type = models.CharField(max_length=100, default="personal_loan")
    currency = models.CharField(max_length=10, default="KES")

    class Meta:
        db_table = "debts"