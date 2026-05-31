"""
debts/views.py

Endpoints:
  GET    /api/debts/              → list all debts with payoff strategies
  POST   /api/debts/              → create debt
  GET    /api/debts/summary/      → total debt overview + payoff strategies
  GET    /api/debts/<id>/         → retrieve debt
  PATCH  /api/debts/<id>/         → update debt
  DELETE /api/debts/<id>/         → delete debt
"""

import logging
from decimal import Decimal

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from .models import Debt
from .serializers import DebtSerializer

logger = logging.getLogger(__name__)


def get_avalanche_order(debts):
    """
    Avalanche strategy — pay highest interest rate first.
    Minimizes total interest paid over time.
    """
    return sorted(debts, key=lambda d: float(d.interest_rate), reverse=True)


def get_snowball_order(debts):
    """
    Snowball strategy — pay smallest balance first.
    Builds momentum through quick wins.
    """
    return sorted(debts, key=lambda d: float(d.current_balance))


def estimate_debt_free_months(debts) -> int | None:
    """
    Estimate total months until all debts are paid off
    based on current monthly payments.
    """
    if not debts:
        return None
    total_balance = sum(d.current_balance for d in debts)
    total_monthly = sum(d.monthly_payment for d in debts)
    if total_monthly <= 0:
        return None
    return int(total_balance / total_monthly)


class DebtListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        debts = Debt.objects.filter(
            user=request.user
        ).order_by("-current_balance")

        # Assign avalanche priority ranks
        avalanche_ordered = get_avalanche_order(list(debts))
        priority_map = {d.id: i + 1 for i, d in enumerate(avalanche_ordered)}

        result = []
        for debt in debts:
            data = DebtSerializer(debt, context={"request": request}).data
            data["avalanche_priority"] = priority_map.get(debt.id, 0)
            result.append(data)

        return Response({
            "debts": result,
            "count": len(result),
        })

    def post(self, request):
        serializer = DebtSerializer(
            data=request.data,
            context={"request": request},
        )
        if serializer.is_valid():
            debt = serializer.save()
            return Response(
                DebtSerializer(debt, context={"request": request}).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(
            {"error": "Invalid data.", "details": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )


class DebtDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_debt(self, debt_id, user):
        try:
            return Debt.objects.get(id=debt_id, user=user)
        except Debt.DoesNotExist:
            return None

    def get(self, request, debt_id):
        debt = self._get_debt(debt_id, request.user)
        if not debt:
            return Response(
                {"error": "Debt not found.", "code": "NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            DebtSerializer(debt, context={"request": request}).data
        )

    def patch(self, request, debt_id):
        debt = self._get_debt(debt_id, request.user)
        if not debt:
            return Response(
                {"error": "Debt not found.", "code": "NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = DebtSerializer(
            debt,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        if serializer.is_valid():
            debt = serializer.save()
            return Response(
                DebtSerializer(debt, context={"request": request}).data
            )
        return Response(
            {"error": "Invalid data.", "details": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def delete(self, request, debt_id):
        debt = self._get_debt(debt_id, request.user)
        if not debt:
            return Response(
                {"error": "Debt not found.", "code": "NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )
        name = debt.name
        debt.delete()
        return Response({"message": f"Debt '{name}' deleted."})


class DebtSummaryView(APIView):
    """
    GET /api/debts/summary/

    Returns total debt overview plus both payoff strategies
    (avalanche and snowball) with recommended order.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        debts = list(Debt.objects.filter(user=request.user))

        if not debts:
            return Response({
                "total_debt": 0,
                "total_monthly_payments": 0,
                "total_paid": 0,
                "debt_count": 0,
                "projected_debt_free_months": None,
                "avalanche_order": [],
                "snowball_order": [],
                "recommendation": "No debts recorded. Add your debts to see payoff strategies.",
            })

        total_debt = sum(d.current_balance for d in debts)
        total_monthly = sum(d.monthly_payment for d in debts)
        total_paid = sum(d.amount_paid for d in debts)
        months_to_free = estimate_debt_free_months(debts)

        # Avalanche — highest interest first
        avalanche = get_avalanche_order(debts)
        avalanche_data = [
            {
                "id": str(d.id),
                "name": d.name,
                "current_balance": d.current_balance,
                "interest_rate": d.interest_rate,
                "monthly_payment": d.monthly_payment,
                "reason": f"{d.interest_rate}% interest — highest rate",
            }
            for d in avalanche
        ]

        # Snowball — smallest balance first
        snowball = get_snowball_order(debts)
        snowball_data = [
            {
                "id": str(d.id),
                "name": d.name,
                "current_balance": d.current_balance,
                "interest_rate": d.interest_rate,
                "monthly_payment": d.monthly_payment,
                "reason": f"{d.currency} {d.current_balance:,.0f} balance — smallest first",
            }
            for d in snowball
        ]

        # Recommendation
        if len(debts) == 1:
            recommendation = "You have one debt. Focus all extra payments on it to pay it off faster."
        elif avalanche[0].interest_rate > 20:
            recommendation = (
                f"Avalanche strategy recommended — your {avalanche[0].name} "
                f"has a {avalanche[0].interest_rate}% rate which is costing you the most."
            )
        else:
            recommendation = (
                "Both strategies work well with your debt profile. "
                "Avalanche saves more money; snowball builds momentum faster."
            )

        return Response({
            "total_debt": total_debt,
            "total_monthly_payments": total_monthly,
            "total_paid": total_paid,
            "debt_count": len(debts),
            "projected_debt_free_months": months_to_free,
            "avalanche_order": avalanche_data,
            "snowball_order": snowball_data,
            "recommendation": recommendation,
        })