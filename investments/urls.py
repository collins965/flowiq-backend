from django.urls import path
from .views import (
    InvestmentListView,
    InvestmentDetailView,
    InvestmentSummaryView,
)

urlpatterns = [
    path("",                            InvestmentListView.as_view(),   name="investment-list"),
    path("summary/",                    InvestmentSummaryView.as_view(),name="investment-summary"),
    path("<uuid:investment_id>/",       InvestmentDetailView.as_view(), name="investment-detail"),
]