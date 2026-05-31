from django.urls import path
from .views import (
    BudgetListView,
    BudgetDetailView,
    BudgetHealthView,
)

urlpatterns = [
    path("",                    BudgetListView.as_view(),   name="budget-list"),
    path("health/",             BudgetHealthView.as_view(), name="budget-health"),
    path("<uuid:budget_id>/",   BudgetDetailView.as_view(), name="budget-detail"),
]