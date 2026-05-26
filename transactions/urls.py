from django.urls import path
from .views import (
    AccountListView,
    AccountDetailView,
    CategoryListView,
    TransactionListView,
    TransactionDetailView,
    TransactionSummaryView,
    ImportHistoryView,
    BulkCategorizeView,
)

# These are mounted at /api/transactions/ in flowiq/urls.py
urlpatterns = [
    # Transactions
    path("",                        TransactionListView.as_view(),    name="transaction-list"),
    path("<uuid:transaction_id>/",  TransactionDetailView.as_view(),  name="transaction-detail"),
    path("summary/",                TransactionSummaryView.as_view(), name="transaction-summary"),
    path("import/history/",         ImportHistoryView.as_view(),      name="import-history"),
    path("bulk-categorize/",        BulkCategorizeView.as_view(),     name="bulk-categorize"),
]

# Accounts — mounted at /api/accounts/ in flowiq/urls.py
account_urlpatterns = [
    path("",                    AccountListView.as_view(),   name="account-list"),
    path("<uuid:account_id>/",  AccountDetailView.as_view(), name="account-detail"),
]

# Categories — mounted at /api/categories/ in flowiq/urls.py
category_urlpatterns = [
    path("", CategoryListView.as_view(), name="category-list"),
]