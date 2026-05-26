from django.db import models
from core.models import BaseModel


class FraudAlert(BaseModel):
    SEVERITY = [("critical", "Critical"), ("high", "High"), ("warning", "Warning")]
    STATUS = [("active", "Active"), ("resolved", "Resolved"), ("false_positive", "False Positive")]

    user_id = models.UUIDField()
    transaction_id = models.UUIDField(null=True, blank=True)
    severity = models.CharField(max_length=20, choices=SEVERITY)
    fraud_type = models.CharField(max_length=255, blank=True)
    ai_analysis = models.TextField(blank=True)
    action_steps = models.TextField(blank=True)
    legal_info = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default="active")

    class Meta:
        db_table = "fraud_alerts"


class FraudDetectionSettings(BaseModel):
    user_id = models.UUIDField(unique=True)
    velocity_threshold = models.IntegerField(default=5)
    amount_multiplier = models.DecimalField(max_digits=4, decimal_places=1, default=3.0)
    night_start = models.IntegerField(default=1)
    night_end = models.IntegerField(default=4)
    trusted_recipients = models.JSONField(default=list)
    email_alerts = models.BooleanField(default=True)
    app_alerts = models.BooleanField(default=True)

    class Meta:
        db_table = "fraud_detection_settings"