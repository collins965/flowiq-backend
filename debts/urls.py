from django.urls import path
from .views import (
    DebtListView,
    DebtDetailView,
    DebtSummaryView,
)

urlpatterns = [
    path("",                    DebtListView.as_view(),    name="debt-list"),
    path("summary/",            DebtSummaryView.as_view(), name="debt-summary"),
    path("<uuid:debt_id>/",     DebtDetailView.as_view(),  name="debt-detail"),
]