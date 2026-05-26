from django.db import models
from core.models import BaseModel


class TaxSettings(BaseModel):
    EMPLOYMENT_TYPES = [
        ("employed", "Employed"),
        ("self_employed", "Self Employed"),
        ("both", "Both"),
    ]

    user_id = models.UUIDField(unique=True)
    country = models.CharField(max_length=100, default="Kenya")
    region = models.CharField(max_length=100, blank=True)
    employment_type = models.CharField(max_length=20, choices=EMPLOYMENT_TYPES, default="employed")
    tax_year = models.CharField(max_length=10, blank=True)
    gross_salary = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    side_hustle_income = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    class Meta:
        db_table = "tax_settings"