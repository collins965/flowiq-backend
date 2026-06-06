from django.urls import path
from .views import (
    TaxSettingsView,
    TaxCalculateView,
    TaxHistoryView,
    TaxRatesView,
)

urlpatterns = [
    path("settings/",   TaxSettingsView.as_view(),  name="tax-settings"),
    path("calculate/",  TaxCalculateView.as_view(),  name="tax-calculate"),
    path("history/",    TaxHistoryView.as_view(),    name="tax-history"),
    path("rates/",      TaxRatesView.as_view(),      name="tax-rates"),
]