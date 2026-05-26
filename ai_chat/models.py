from django.db import models
from core.models import BaseModel


class AIConversation(BaseModel):
    user_id = models.UUIDField()
    messages = models.JSONField(default=list)

    class Meta:
        db_table = "ai_conversations"