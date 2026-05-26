from django.db import models
from core.models import BaseModel


class Subscription(BaseModel):
    PLANS = [("free", "Free"), ("pro", "Pro"), ("business", "Business")]
    STATUS = [("pending", "Pending"), ("active", "Active"), ("expired", "Expired"), ("cancelled", "Cancelled")]

    user_id = models.UUIDField()
    plan = models.CharField(max_length=20, choices=PLANS)
    billing_period = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default="KES")
    flutterwave_tx_id = models.CharField(max_length=255, blank=True)
    payment_method = models.CharField(max_length=50, default="card")
    status = models.CharField(max_length=20, choices=STATUS, default="pending")
    starts_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        db_table = "subscriptions"