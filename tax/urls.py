from django.urls import path
from .views import TaxCalculateView

urlpatterns = [
    path("calculate/", TaxCalculateView.as_view(), name="tax-calculate"),
]