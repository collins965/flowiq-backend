from django.urls import path
from .views import (
    AccountListView,
    AccountDetailView,
    AccountSummaryView,
)

urlpatterns = [
    path("",                        AccountListView.as_view(),   name="account-list"),
    path("summary/",                AccountSummaryView.as_view(),name="account-summary"),
    path("<uuid:account_id>/",      AccountDetailView.as_view(), name="account-detail"),
]