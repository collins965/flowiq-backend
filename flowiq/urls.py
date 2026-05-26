from django.urls import path, include
from transactions.urls import account_urlpatterns, category_urlpatterns

urlpatterns = [
    path("api/tax/", include("tax.urls")),
    path("api/chat/", include("ai_chat.urls")),
    path("api/location/", include("location.urls")),
    path("api/fraud/", include("fraud.urls")),
    path("api/reports/", include("reports.urls")),
    path("api/transactions/", include("transactions.urls")),
    path("api/accounts/", include("accounts.urls")),
    path("api/budgets/", include("budgets.urls")),
    path("api/savings/", include("savings.urls")),
    path("api/debts/", include("debts.urls")),
    path("api/investments/", include("investments.urls")),
    path("api/notifications/", include("notifications.urls")),
    path("api/payments/", include("payments.urls")),
    path("api/transactions/", include("transactions.urls")),
    path("api/accounts/",     include((account_urlpatterns, "accounts"))),
    path("api/categories/",   include((category_urlpatterns, "categories"))),
    path("api/chat/",         include("ai_chat.urls")),
]