"""
budgets/views.py

Endpoints:
  GET    /api/budgets/              → list budgets with actual spend
  POST   /api/budgets/              → create budget
  GET    /api/budgets/<id>/         → retrieve budget
  PATCH  /api/budgets/<id>/         → update budget
  DELETE /api/budgets/<id>/         → delete budget
  GET    /api/budgets/health/       → budget health score
"""

import logging
from decimal import Decimal
from datetime import date, timedelta

from django.db.models import Sum, Q
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from .models import Budget
from .serializers import BudgetSerializer, BudgetHealthSerializer
from transactions.models import Transaction

logger = logging.getLogger(__name__)


def get_period_dates(period: str, start_date: date):
    """
    Returns (date_from, date_to) for the current budget period.
    """
    today = timezone.now().date()

    if period == "monthly":
        date_from = today.replace(day=1)
        # Last day of current month
        if today.month == 12:
            date_to = today.replace(month=12, day=31)
        else:
            date_to = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
    elif period == "weekly":
        # Start of current week (Monday)
        date_from = today - timedelta(days=today.weekday())
        date_to = date_from + timedelta(days=6)
    else:
        date_from = today.replace(day=1)
        date_to = today

    return date_from, date_to


def calculate_projected_spend(amount_spent: Decimal, period: str) -> Decimal:
    """
    Project end-of-period spend based on current daily rate.
    """
    today = timezone.now().date()

    if period == "monthly":
        days_elapsed = today.day
        days_in_month = 30  # approximate
        if days_elapsed == 0:
            return Decimal("0")
        daily_rate = amount_spent / days_elapsed
        return daily_rate * days_in_month
    elif period == "weekly":
        day_of_week = today.weekday() + 1  # 1-7
        if day_of_week == 0:
            return Decimal("0")
        daily_rate = amount_spent / day_of_week
        return daily_rate * 7

    return amount_spent


def annotate_budget_with_spend(budget: Budget, user) -> dict:
    """
    Calculate actual spending for a budget category in the current period.
    Returns a dict of computed fields to inject into the serializer.
    """
    date_from, date_to = get_period_dates(budget.period, budget.start_date)

    # Sum expenses in this category for the current period
    spent_result = Transaction.objects.filter(
        user=user,
        category=budget.category,
        type="expense",
        date__gte=date_from,
        date__lte=date_to,
        is_duplicate=False,
    ).aggregate(total=Sum("amount_base_currency"))

    amount_spent = abs(spent_result["total"] or Decimal("0"))
    amount_remaining = max(Decimal("0"), budget.amount - amount_spent)
    percent_used = float(
        (amount_spent / budget.amount * 100) if budget.amount > 0 else 0
    )
    is_over_budget = amount_spent > budget.amount
    projected_spend = calculate_projected_spend(amount_spent, budget.period)

    return {
        "amount_spent": amount_spent,
        "amount_remaining": amount_remaining,
        "percent_used": round(percent_used, 1),
        "is_over_budget": is_over_budget,
        "projected_spend": projected_spend,
    }


class BudgetListView(APIView):
    """
    GET  — list all budgets with real-time spend data
    POST — create a new budget
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        budgets = (
            Budget.objects
            .filter(user=request.user)
            .select_related("category")
            .order_by("category__name")
        )

        result = []
        for budget in budgets:
            spend_data = annotate_budget_with_spend(budget, request.user)
            serializer = BudgetSerializer(budget, context={"request": request})
            data = serializer.data
            data.update(spend_data)
            result.append(data)

        return Response({
            "budgets": result,
            "count": len(result),
        })

    def post(self, request):
        serializer = BudgetSerializer(
            data=request.data,
            context={"request": request},
        )
        if serializer.is_valid():
            budget = serializer.save()
            # Return with spend data
            spend_data = annotate_budget_with_spend(budget, request.user)
            data = BudgetSerializer(budget, context={"request": request}).data
            data.update(spend_data)
            return Response(data, status=status.HTTP_201_CREATED)
        return Response(
            {"error": "Invalid data.", "details": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )


class BudgetDetailView(APIView):
    """
    GET    — retrieve single budget with spend data
    PATCH  — update budget amount, period, or note
    DELETE — delete budget
    """
    permission_classes = [IsAuthenticated]

    def _get_budget(self, budget_id, user):
        try:
            return Budget.objects.select_related("category").get(
                id=budget_id, user=user
            )
        except Budget.DoesNotExist:
            return None

    def get(self, request, budget_id):
        budget = self._get_budget(budget_id, request.user)
        if not budget:
            return Response(
                {"error": "Budget not found.", "code": "NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )
        spend_data = annotate_budget_with_spend(budget, request.user)
        data = BudgetSerializer(budget, context={"request": request}).data
        data.update(spend_data)
        return Response(data)

    def patch(self, request, budget_id):
        budget = self._get_budget(budget_id, request.user)
        if not budget:
            return Response(
                {"error": "Budget not found.", "code": "NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = BudgetSerializer(
            budget,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        if serializer.is_valid():
            budget = serializer.save()
            spend_data = annotate_budget_with_spend(budget, request.user)
            data = BudgetSerializer(budget, context={"request": request}).data
            data.update(spend_data)
            return Response(data)
        return Response(
            {"error": "Invalid data.", "details": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def delete(self, request, budget_id):
        budget = self._get_budget(budget_id, request.user)
        if not budget:
            return Response(
                {"error": "Budget not found.", "code": "NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )
        name = budget.category.name
        budget.delete()
        return Response({"message": f"Budget for '{name}' deleted."})


class BudgetHealthView(APIView):
    """
    GET /api/budgets/health/

    Returns a 0-100 health score based on:
    - % of categories within budget
    - Savings rate
    - Over-budget severity
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        budgets = (
            Budget.objects
            .filter(user=request.user)
            .select_related("category")
        )

        if not budgets.exists():
            return Response({
                "score": 0,
                "label": "No budgets set",
                "color": "#6B7280",
                "total_budgeted": 0,
                "total_spent": 0,
                "categories_over_budget": 0,
                "categories_at_risk": 0,
                "categories_on_track": 0,
                "ai_summary": "You haven't set any budgets yet. Start by adding budgets for your main spending categories.",
            })

        total_budgeted = Decimal("0")
        total_spent = Decimal("0")
        over_budget = 0
        at_risk = 0
        on_track = 0

        for budget in budgets:
            spend_data = annotate_budget_with_spend(budget, request.user)
            total_budgeted += budget.amount
            total_spent += spend_data["amount_spent"]
            percent = spend_data["percent_used"]

            if percent > 100:
                over_budget += 1
            elif percent > 80:
                at_risk += 1
            else:
                on_track += 1

        total = over_budget + at_risk + on_track

        # Score calculation
        if total == 0:
            score = 100
        else:
            on_track_weight = (on_track / total) * 60
            at_risk_weight = (at_risk / total) * 30
            over_weight = (over_budget / total) * 0

            overall_percent = float(
                total_spent / total_budgeted * 100
            ) if total_budgeted > 0 else 0

            spend_score = max(0, 40 - (max(0, overall_percent - 70) * 0.8))
            score = int(on_track_weight + at_risk_weight + spend_score)
            score = max(0, min(100, score))

        # Label and color
        if score >= 80:
            label = "Excellent"
            color = "#10B981"
        elif score >= 60:
            label = "Good"
            color = "#3B82F6"
        elif score >= 40:
            label = "Fair"
            color = "#F59E0B"
        else:
            label = "Needs Attention"
            color = "#EF4444"

        # Simple AI summary (full AI via the chat endpoint)
        if over_budget > 0:
            ai_summary = (
                f"{over_budget} categor{'y' if over_budget == 1 else 'ies'} "
                f"over budget this month. Focus on reducing those first."
            )
        elif at_risk > 0:
            ai_summary = (
                f"Looking good overall — {at_risk} categor{'y' if at_risk == 1 else 'ies'} "
                f"approaching the limit. Keep an eye on spending this week."
            )
        else:
            ai_summary = "All categories are within budget. Great financial discipline this month."

        return Response({
            "score": score,
            "label": label,
            "color": color,
            "total_budgeted": total_budgeted,
            "total_spent": total_spent,
            "categories_over_budget": over_budget,
            "categories_at_risk": at_risk,
            "categories_on_track": on_track,
            "ai_summary": ai_summary,
        })