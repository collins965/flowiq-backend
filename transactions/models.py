"""
transactions/models.py

Account is defined in the accounts app.
We reference it here using "accounts.Account" string notation
so Django resolves it at runtime without a circular import.
"""

import uuid
from django.db import models
from django.conf import settings


class Category(models.Model):
    CATEGORY_TYPES = [
        ("income", "Income"),
        ("expense", "Expense"),
        ("both", "Both"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="categories",
        null=True,
        blank=True,  # null for system categories
    )

    name = models.CharField(max_length=100)
    icon = models.CharField(max_length=50, default="circle")
    color = models.CharField(max_length=7, default="#6366F1")
    type = models.CharField(max_length=10, choices=CATEGORY_TYPES, default="expense")
    is_system = models.BooleanField(default=False)

    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="subcategories",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "categories"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["type"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "name"],
                condition=models.Q(user__isnull=False),
                name="unique_user_category_name",
            )
        ]

    def __str__(self):
        return self.name


class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ("income", "Income"),
        ("expense", "Expense"),
        ("transfer", "Transfer"),
    ]
    SOURCE_TYPES = [
        ("manual", "Manual Entry"),
        ("import", "File Import"),
        ("api", "API/Bank Feed"),
    ]
    FRAUD_STATUS = [
        ("clear", "Clear"),
        ("flagged", "Flagged"),
        ("reviewed", "Reviewed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="transactions",
    )

    # String reference to accounts.Account — avoids circular imports
    account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
    )

    # Core fields
    date = models.DateField()
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.CharField(max_length=3, default="KES")
    amount_base_currency = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Amount converted to user's base currency",
    )
    description = models.TextField(blank=True, default="")
    merchant = models.CharField(max_length=200, blank=True, default="")
    type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    source = models.CharField(max_length=20, choices=SOURCE_TYPES, default="manual")

    # Fraud
    fraud_status = models.CharField(
        max_length=20, choices=FRAUD_STATUS, default="clear"
    )
    fraud_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    # Metadata
    is_duplicate = models.BooleanField(default=False)
    notes = models.TextField(blank=True, default="")
    receipt_url = models.URLField(blank=True, default="")
    raw_data = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "transactions"
        ordering = ["-date", "-created_at"]
        indexes = [
            models.Index(fields=["user", "-date"]),
            models.Index(fields=["user", "type"]),
            models.Index(fields=["user", "category"]),
            models.Index(fields=["user", "fraud_status"]),
            models.Index(fields=["user", "date", "amount"]),
        ]

    def __str__(self):
        label = self.merchant or self.description or "Transaction"
        return f"{label} | {self.currency} {self.amount}"

    @property
    def signed_amount(self):
        """Negative for expenses, positive for income."""
        if self.type == "expense":
            return -abs(self.amount)
        return abs(self.amount)

    @property
    def is_income(self):
        return self.type == "income"

    @property
    def is_expense(self):
        return self.type == "expense"


class ImportHistory(models.Model):
    STATUS_CHOICES = [
        ("processing", "Processing"),
        ("complete", "Complete"),
        ("failed", "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="imports",
    )

    # String reference to accounts.Account
    account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    filename = models.CharField(max_length=255)
    file_format = models.CharField(max_length=20)
    source_bank = models.CharField(max_length=100, blank=True, default="")
    transaction_count = models.PositiveIntegerField(default=0)
    duplicates_removed = models.PositiveIntegerField(default=0)
    date_range_start = models.DateField(null=True, blank=True)
    date_range_end = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="processing"
    )
    error_message = models.TextField(blank=True, default="")
    ai_summary = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "import_history"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.filename} ({self.status})"