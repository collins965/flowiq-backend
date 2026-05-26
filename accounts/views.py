"""
accounts/views.py

Endpoints:
  GET    /api/accounts/           → list user's accounts
  POST   /api/accounts/           → create account
  GET    /api/accounts/<id>/      → retrieve account
  PATCH  /api/accounts/<id>/      → update account
  DELETE /api/accounts/<id>/      → deactivate account
  GET    /api/accounts/summary/   → total balance across all accounts
"""

import logging
from decimal import Decimal

from django.db.models import Sum

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from .models import Account
from .serializers import AccountSerializer, AccountListSerializer

logger = logging.getLogger(__name__)


class AccountListView(APIView):
    """
    GET  — list all active accounts for the current user
    POST — create a new account
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        accounts = (
            Account.objects
            .filter(user=request.user, is_active=True)
            .order_by("name")
        )
        serializer = AccountListSerializer(accounts, many=True)
        return Response({
            "accounts": serializer.data,
            "count": accounts.count(),
        })

    def post(self, request):
        # Check plan limits — free users can only have 1 account
        plan = getattr(getattr(request.user, "profile", None), "plan", "free")
        if plan == "free":
            existing_count = Account.objects.filter(
                user=request.user, is_active=True
            ).count()
            if existing_count >= 1:
                return Response(
                    {
                        "error": "Free plan is limited to 1 account. Upgrade to Pro for unlimited accounts.",
                        "code": "PLAN_LIMIT_REACHED",
                        "upgrade_required": True,
                    },
                    status=status.HTTP_402_PAYMENT_REQUIRED,
                )

        serializer = AccountSerializer(
            data=request.data,
            context={"request": request},
        )
        if serializer.is_valid():
            account = serializer.save()
            return Response(
                AccountSerializer(account, context={"request": request}).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(
            {"error": "Invalid data.", "details": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )


class AccountDetailView(APIView):
    """
    GET    — retrieve a single account
    PATCH  — update account fields
    DELETE — soft delete (mark inactive)
    """
    permission_classes = [IsAuthenticated]

    def _get_account(self, account_id, user):
        try:
            return Account.objects.get(id=account_id, user=user)
        except Account.DoesNotExist:
            return None

    def get(self, request, account_id):
        account = self._get_account(account_id, request.user)
        if not account:
            return Response(
                {"error": "Account not found.", "code": "NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = AccountSerializer(account, context={"request": request})
        return Response(serializer.data)

    def patch(self, request, account_id):
        account = self._get_account(account_id, request.user)
        if not account:
            return Response(
                {"error": "Account not found.", "code": "NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = AccountSerializer(
            account,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(
            {"error": "Invalid data.", "details": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def delete(self, request, account_id):
        account = self._get_account(account_id, request.user)
        if not account:
            return Response(
                {"error": "Account not found.", "code": "NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )
        # Soft delete — keep the record so linked transactions stay intact
        account.is_active = False
        account.save(update_fields=["is_active", "updated_at"])
        return Response({"message": f"Account '{account.name}' deactivated."})


class AccountSummaryView(APIView):
    """
    GET /api/accounts/summary/

    Returns total balance across all accounts grouped by currency.
    Used on the dashboard net worth card.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        accounts = Account.objects.filter(
            user=request.user, is_active=True
        )

        # Group balances by currency
        currency_totals = {}
        for account in accounts:
            currency = account.currency
            if currency not in currency_totals:
                currency_totals[currency] = Decimal("0")
            currency_totals[currency] += account.balance

        # Get user's base currency from profile
        profile = getattr(request.user, "profile", None)
        base_currency = getattr(profile, "currency_code", "KES")

        # Total in base currency (same currency only for now —
        # exchange rate conversion will be added later)
        base_total = currency_totals.get(base_currency, Decimal("0"))

        return Response({
            "total_balance": base_total,
            "base_currency": base_currency,
            "by_currency": currency_totals,
            "account_count": accounts.count(),
            "accounts": AccountListSerializer(accounts, many=True).data,
        })