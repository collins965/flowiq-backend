"""
investments/views.py

Endpoints:
  GET    /api/investments/            → list all investments + portfolio summary
  POST   /api/investments/            → add investment
  GET    /api/investments/summary/    → portfolio overview
  GET    /api/investments/<id>/       → retrieve investment
  PATCH  /api/investments/<id>/       → update investment
  DELETE /api/investments/<id>/       → delete investment
"""

import logging
from decimal import Decimal
from collections import defaultdict

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from .models import Investment, InvestmentType
from .serializers import InvestmentSerializer

logger = logging.getLogger(__name__)


class InvestmentListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        investments = Investment.objects.filter(
            user=request.user
        ).order_by("-current_value")

        serializer = InvestmentSerializer(
            investments, many=True, context={"request": request}
        )
        return Response({
            "investments": serializer.data,
            "count": investments.count(),
        })

    def post(self, request):
        serializer = InvestmentSerializer(
            data=request.data,
            context={"request": request},
        )
        if serializer.is_valid():
            investment = serializer.save()
            return Response(
                InvestmentSerializer(
                    investment, context={"request": request}
                ).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(
            {"error": "Invalid data.", "details": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )


class InvestmentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_investment(self, investment_id, user):
        try:
            return Investment.objects.get(id=investment_id, user=user)
        except Investment.DoesNotExist:
            return None

    def get(self, request, investment_id):
        investment = self._get_investment(investment_id, request.user)
        if not investment:
            return Response(
                {"error": "Investment not found.", "code": "NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            InvestmentSerializer(
                investment, context={"request": request}
            ).data
        )

    def patch(self, request, investment_id):
        investment = self._get_investment(investment_id, request.user)
        if not investment:
            return Response(
                {"error": "Investment not found.", "code": "NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = InvestmentSerializer(
            investment,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        if serializer.is_valid():
            investment = serializer.save()
            return Response(
                InvestmentSerializer(
                    investment, context={"request": request}
                ).data
            )
        return Response(
            {"error": "Invalid data.", "details": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def delete(self, request, investment_id):
        investment = self._get_investment(investment_id, request.user)
        if not investment:
            return Response(
                {"error": "Investment not found.", "code": "NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )
        name = investment.name
        investment.delete()
        return Response({"message": f"Investment '{name}' deleted."})


class InvestmentSummaryView(APIView):
    """
    GET /api/investments/summary/

    Returns full portfolio overview:
    - Total invested, total current value, total gain/loss
    - Return percentage across entire portfolio
    - Breakdown by investment type
    - Best and worst performing investments
    - Kenya-specific investment platform links
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        investments = list(
            Investment.objects.filter(user=request.user)
        )

        if not investments:
            return Response({
                "total_invested": 0,
                "total_current_value": 0,
                "total_gain_loss": 0,
                "total_return_percent": 0,
                "investment_count": 0,
                "by_type": [],
                "best_performer": None,
                "worst_performer": None,
                "kenya_platforms": self._kenya_platforms(),
                "message": "No investments recorded yet. Add your first investment to get started.",
            })

        total_invested = sum(i.amount_invested for i in investments)
        total_current = sum(i.current_value for i in investments)
        total_gain_loss = total_current - total_invested
        total_return = float(
            total_gain_loss / total_invested * 100
        ) if total_invested > 0 else 0

        # Breakdown by type
        by_type = defaultdict(lambda: {
            "total_invested": Decimal("0"),
            "total_current_value": Decimal("0"),
            "count": 0,
        })
        for inv in investments:
            by_type[inv.investment_type]["total_invested"] += inv.amount_invested
            by_type[inv.investment_type]["total_current_value"] += inv.current_value
            by_type[inv.investment_type]["count"] += 1

        by_type_list = []
        for inv_type, data in by_type.items():
            gain = data["total_current_value"] - data["total_invested"]
            ret = float(
                gain / data["total_invested"] * 100
            ) if data["total_invested"] > 0 else 0
            allocation = float(
                data["total_current_value"] / total_current * 100
            ) if total_current > 0 else 0
            by_type_list.append({
                "type": inv_type,
                "type_display": dict(InvestmentType.choices).get(inv_type, inv_type),
                "total_invested": data["total_invested"],
                "total_current_value": data["total_current_value"],
                "gain_loss": gain,
                "return_percent": round(ret, 2),
                "count": data["count"],
                "allocation_percent": round(allocation, 1),
            })

        # Sort by current value descending
        by_type_list.sort(key=lambda x: float(x["total_current_value"]), reverse=True)

        # Best and worst performers
        sorted_by_return = sorted(
            investments, key=lambda i: i.return_percent, reverse=True
        )
        best = sorted_by_return[0] if sorted_by_return else None
        worst = sorted_by_return[-1] if len(sorted_by_return) > 1 else None

        return Response({
            "total_invested": total_invested,
            "total_current_value": total_current,
            "total_gain_loss": total_gain_loss,
            "total_return_percent": round(total_return, 2),
            "investment_count": len(investments),
            "by_type": by_type_list,
            "best_performer": InvestmentSerializer(
                best, context={"request": request}
            ).data if best else None,
            "worst_performer": InvestmentSerializer(
                worst, context={"request": request}
            ).data if worst else None,
            "kenya_platforms": self._kenya_platforms(),
        })

    def _kenya_platforms(self) -> list:
        """Kenya-specific investment platform reference links."""
        return [
            {"name": "Cytonn Money Market", "url": "https://cytonn.com", "type": "money_market"},
            {"name": "CIC Money Market", "url": "https://cic.co.ke", "type": "money_market"},
            {"name": "Sanlam Money Market", "url": "https://sanlam.co.ke", "type": "money_market"},
            {"name": "M-Akiba", "url": "https://m-akiba.go.ke", "type": "treasury"},
            {"name": "NSE (Nairobi Securities Exchange)", "url": "https://nse.co.ke", "type": "stock"},
            {"name": "CDH Investment Bank", "url": "https://cdhib.com", "type": "stock"},
        ]