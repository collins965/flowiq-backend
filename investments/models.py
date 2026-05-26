from django.db import models
from core.models import BaseModel


class Investment(BaseModel):
    user_id = models.UUIDField()
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=100, blank=True)
    amount_invested = models.DecimalField(max_digits=15, decimal_places=2)
    current_value = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.CharField(max_length=10, default="KES")
    start_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "investments"