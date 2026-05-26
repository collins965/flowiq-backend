from django.db import models
from core.models import BaseModel


class Report(BaseModel):
    user_id = models.UUIDField()
    type = models.CharField(max_length=50)
    title = models.CharField(max_length=255)
    parameters = models.JSONField(default=dict)
    data = models.JSONField(default=dict)
    ai_narrative = models.TextField(blank=True)
    file_url = models.URLField(blank=True)
    status = models.CharField(max_length=20, default="generating")

    class Meta:
        db_table = "reports"