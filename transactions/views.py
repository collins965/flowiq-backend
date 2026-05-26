"""
transactions/views.py

Endpoints:
  GET/POST        /api/transactions/                 → list + create
  GET/PATCH/DEL   /api/transactions/<id>/            → detail
  GET             /api/transactions/summary/         → dashboard KPIs
  GET             /api/transactions/import/history/  → past imports
  GET/POST        /api/accounts/                     → accounts
  GET/PATCH/DEL   /api/accounts/<id>/                → account detail
  GET/POST        /api/categories/                   → categories
"""

import logging
from decimal import Decimal
from datetime import date, timedelta

from django.db.models import Sum, Count, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from accounts.models import Account
from .models import Category, Transaction, ImportHistory
from .serializers import (
    AccountSerializer,
    CategorySerializer,
    TransactionSerializer,
    TransactionListSerializer,
    ImportHistorySerializer,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Accounts
# ─────────────────────────────────────────────────────────────────────────────

class AccountListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        accounts = Account.objects.filter(
            user=request.user, is_active=True
        ).order_by("name")
        serializer = AccountSerializer(accounts, many=True)
        return Response({"accounts": serializer.data})

    def post(self, request):
        serializer = AccountSerializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(
            {"error": "Invalid data.", "details": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )


class AccountDetailView(APIView):
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
        return Response(AccountSerializer(account).data)

    def patch(self, request, account_id):
        account = self._get_account(account_id, request.user)
        if not account:
            return Response(
                {"error": "Account not found.", "code": "NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = AccountSerializer(
            account, data=request.data, partial=True,
            context={"request": request}
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
        # Soft delete — mark inactive instead of deleting
        account.is_active = False
        account.save(update_fields=["is_active"])
        return Response({"message": "Account deactivated."})


# ─────────────────────────────────────────────────────────────────────────────
# Categories
# ─────────────────────────────────────────────────────────────────────────────

class CategoryListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Return system categories + user's own categories
        categories = Category.objects.filter(
            Q(is_system=True) | Q(user=request.user)
        ).order_by("name")
        serializer = CategorySerializer(categories, many=True)
        return Response({"categories": serializer.data})

    def post(self, request):
        serializer = CategorySerializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(
            {"error": "Invalid data.", "details": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Transactions
# ─────────────────────────────────────────────────────────────────────────────

class TransactionListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        List transactions with optional filters.

        Query params:
          date_from     YYYY-MM-DD
          date_to       YYYY-MM-DD
          type          income | expense | transfer
          category      category UUID
          account       account UUID
          fraud_status  clear | flagged | reviewed
          search        text search on merchant + description
          page          page number (default 1)
          page_size     results per page (default 25, max 100)
        """
        qs = Transaction.objects.filter(
            user=request.user
        ).select_related("category", "account")

        # --- Filters ---
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        tx_type = request.query_params.get("type")
        category_id = request.query_params.get("category")
        account_id = request.query_params.get("account")
        fraud_status = request.query_params.get("fraud_status")
        search = request.query_params.get("search", "").strip()

        if date_from:
            try:
                qs = qs.filter(date__gte=date_from)
            except ValueError:
                pass

        if date_to:
            try:
                qs = qs.filter(date__lte=date_to)
            except ValueError:
                pass

        if tx_type in ("income", "expense", "transfer"):
            qs = qs.filter(type=tx_type)

        if category_id:
            qs = qs.filter(category_id=category_id)

        if account_id:
            qs = qs.filter(account_id=account_id)

        if fraud_status in ("clear", "flagged", "reviewed"):
            qs = qs.filter(fraud_status=fraud_status)

        if search:
            qs = qs.filter(
                Q(merchant__icontains=search) |
                Q(description__icontains=search) |
                Q(notes__icontains=search)
            )

        # --- Pagination ---
        try:
            page = max(1, int(request.query_params.get("page", 1)))
            page_size = min(100, max(1, int(request.query_params.get("page_size", 25))))
        except (ValueError, TypeError):
            page, page_size = 1, 25

        total = qs.count()
        offset = (page - 1) * page_size
        transactions = qs[offset: offset + page_size]

        serializer = TransactionListSerializer(transactions, many=True)
        return Response({
            "transactions": serializer.data,
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_next": offset + page_size < total,
        })

    def post(self, request):
        """Create a single manual transaction."""
        serializer = TransactionSerializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            transaction = serializer.save()
            return Response(
                TransactionSerializer(transaction, context={"request": request}).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(
            {"error": "Invalid transaction data.", "details": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )


class TransactionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_transaction(self, transaction_id, user):
        try:
            return Transaction.objects.select_related(
                "category", "account"
            ).get(id=transaction_id, user=user)
        except Transaction.DoesNotExist:
            return None

    def get(self, request, transaction_id):
        tx = self._get_transaction(transaction_id, request.user)
        if not tx:
            return Response(
                {"error": "Transaction not found.", "code": "NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            TransactionSerializer(tx, context={"request": request}).data
        )

    def patch(self, request, transaction_id):
        tx = self._get_transaction(transaction_id, request.user)
        if not tx:
            return Response(
                {"error": "Transaction not found.", "code": "NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = TransactionSerializer(
            tx, data=request.data, partial=True,
            context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(
            {"error": "Invalid data.", "details": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def delete(self, request, transaction_id):
        tx = self._get_transaction(transaction_id, request.user)
        if not tx:
            return Response(
                {"error": "Transaction not found.", "code": "NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )
        tx.delete()
        return Response({"message": "Transaction deleted."})


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard summary
# ─────────────────────────────────────────────────────────────────────────────

class TransactionSummaryView(APIView):
    """
    GET /api/transactions/summary/

    Query params:
      period   this_month | last_month | last_3m | last_6m | this_year | all
               default: this_month
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        period = request.query_params.get("period", "this_month")
        today = timezone.now().date()

        # Determine date range
        if period == "this_month":
            date_from = today.replace(day=1)
            date_to = today
        elif period == "last_month":
            first_this = today.replace(day=1)
            last_month_end = first_this - timedelta(days=1)
            date_from = last_month_end.replace(day=1)
            date_to = last_month_end
        elif period == "last_3m":
            date_from = (today - timedelta(days=90))
            date_to = today
        elif period == "last_6m":
            date_from = (today - timedelta(days=180))
            date_to = today
        elif period == "this_year":
            date_from = today.replace(month=1, day=1)
            date_to = today
        else:
            date_from = None
            date_to = today

        qs = Transaction.objects.filter(
            user=request.user,
            is_duplicate=False,
        )
        if date_from:
            qs = qs.filter(date__gte=date_from)
        qs = qs.filter(date__lte=date_to)

        # Aggregates
        income_qs = qs.filter(type="income")
        expense_qs = qs.filter(type="expense")

        total_income = income_qs.aggregate(
            total=Sum("amount_base_currency")
        )["total"] or Decimal("0")

        total_expenses = expense_qs.aggregate(
            total=Sum("amount_base_currency")
        )["total"] or Decimal("0")

        net_cashflow = total_income - total_expenses
        tx_count = qs.count()

        # Top spending categories
        top_categories = (
            expense_qs
            .values("category__name", "category__color", "category__icon")
            .annotate(total=Sum("amount_base_currency"), count=Count("id"))
            .order_by("-total")[:8]
        )

        # Monthly trend (last 6 months)
        monthly_trend = (
            qs
            .filter(date__gte=today - timedelta(days=180))
            .annotate(month=TruncMonth("date"))
            .values("month", "type")
            .annotate(total=Sum("amount_base_currency"))
            .order_by("month")
        )

        # Fraud count
        fraud_count = qs.filter(fraud_status="flagged").count()

        return Response({
            "period": period,
            "date_from": str(date_from) if date_from else None,
            "date_to": str(date_to),
            "total_income": total_income,
            "total_expenses": total_expenses,
            "net_cashflow": net_cashflow,
            "transaction_count": tx_count,
            "fraud_flagged_count": fraud_count,
            "top_categories": list(top_categories),
            "monthly_trend": list(monthly_trend),
        })


# ─────────────────────────────────────────────────────────────────────────────
# Import history
# ─────────────────────────────────────────────────────────────────────────────

class ImportHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        imports = ImportHistory.objects.filter(
            user=request.user
        ).order_by("-created_at")[:50]
        serializer = ImportHistorySerializer(imports, many=True)
        return Response({"imports": serializer.data})


# ─────────────────────────────────────────────────────────────────────────────
# Bulk operations
# ─────────────────────────────────────────────────────────────────────────────

class BulkCategorizeView(APIView):
    """
    PATCH /api/transactions/bulk-categorize/
    Body: { "transaction_ids": ["uuid1", "uuid2"], "category_id": "uuid" }
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        transaction_ids = request.data.get("transaction_ids", [])
        category_id = request.data.get("category_id")

        if not transaction_ids or not category_id:
            return Response(
                {"error": "transaction_ids and category_id are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate category belongs to user or is system
        from django.db.models import Q as DQ
        try:
            category = Category.objects.get(
                DQ(user=request.user) | DQ(is_system=True),
                id=category_id,
            )
        except Category.DoesNotExist:
            return Response(
                {"error": "Category not found.", "code": "NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )

        updated = Transaction.objects.filter(
            id__in=transaction_ids,
            user=request.user,
        ).update(category=category)

        return Response({"updated": updated, "category": category.name})