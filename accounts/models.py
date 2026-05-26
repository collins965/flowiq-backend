import uuid
from django.db import models
from django.conf import settings
from core.models import BaseModel


class Account(BaseModel):
    ACCOUNT_TYPES = [
        ("bank", "Bank"),
        ("mobile_money", "Mobile Money"),
        ("cash", "Cash"),
        ("investment", "Investment"),
        ("credit_card", "Credit Card"),
        ("crypto", "Crypto"),
    ]

    # Proper ForeignKey — not a plain UUIDField
    # This gives you account.user, cascade deletes, and proper ORM queries
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="accounts",
        null=True,   
        blank=True,  
    )

    name = models.CharField(max_length=255)
    type = models.CharField(max_length=50, choices=ACCOUNT_TYPES)
    currency = models.CharField(max_length=10, default="KES")
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    institution_name = models.CharField(max_length=255, blank=True, default="")
    is_active = models.BooleanField(default=True)

    class Meta:
        # No db_table override — Django uses the default "accounts_account"
        # This removes the clash with transactions app
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["user", "type"]),
            models.Index(fields=["user", "is_active"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.user})"