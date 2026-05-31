"""
savings/views.py

Endpoints:
  GET    /api/savings/                      → list all goals
  POST   /api/savings/                      → create goal
  GET    /api/savings/<id>/                 → retrieve goal
  PATCH  /api/savings/<id>/                 → update goal
  DELETE /api/savings/<id>/                 → delete goal
  POST   /api/savings/<id>/contribute/      → add contribution
  GET    /api/savings/<id>/contributions/   → list contributions
"""

import logging
from decimal import Decimal

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from .models import SavingsGoal, GoalContribution
from .serializers import SavingsGoalSerializer, GoalContributionSerializer

logger = logging.getLogger(__name__)


class SavingsGoalListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        filter_type = request.query_params.get("filter", "active")

        qs = SavingsGoal.objects.filter(user=request.user)

        if filter_type == "active":
            qs = qs.filter(is_complete=False)
        elif filter_type == "complete":
            qs = qs.filter(is_complete=True)
        # filter_type == "all" returns everything

        qs = qs.prefetch_related("contributions").order_by("-created_at")

        serializer = SavingsGoalSerializer(
            qs, many=True, context={"request": request}
        )

        # Summary stats
        total_saved = sum(g.current_amount for g in qs)
        total_target = sum(g.target_amount for g in qs)

        return Response({
            "goals": serializer.data,
            "count": qs.count(),
            "total_saved": total_saved,
            "total_target": total_target,
        })

    def post(self, request):
        serializer = SavingsGoalSerializer(
            data=request.data,
            context={"request": request},
        )
        if serializer.is_valid():
            goal = serializer.save()
            return Response(
                SavingsGoalSerializer(goal, context={"request": request}).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(
            {"error": "Invalid data.", "details": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )


class SavingsGoalDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_goal(self, goal_id, user):
        try:
            return SavingsGoal.objects.prefetch_related(
                "contributions"
            ).get(id=goal_id, user=user)
        except SavingsGoal.DoesNotExist:
            return None

    def get(self, request, goal_id):
        goal = self._get_goal(goal_id, request.user)
        if not goal:
            return Response(
                {"error": "Goal not found.", "code": "NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            SavingsGoalSerializer(goal, context={"request": request}).data
        )

    def patch(self, request, goal_id):
        goal = self._get_goal(goal_id, request.user)
        if not goal:
            return Response(
                {"error": "Goal not found.", "code": "NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = SavingsGoalSerializer(
            goal,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        if serializer.is_valid():
            goal = serializer.save()
            return Response(
                SavingsGoalSerializer(goal, context={"request": request}).data
            )
        return Response(
            {"error": "Invalid data.", "details": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def delete(self, request, goal_id):
        goal = self._get_goal(goal_id, request.user)
        if not goal:
            return Response(
                {"error": "Goal not found.", "code": "NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )
        name = goal.name
        goal.delete()
        return Response({"message": f"Goal '{name}' deleted."})


class GoalContributeView(APIView):
    """
    POST /api/savings/<id>/contribute/
    Body: { "amount": 5000, "note": "Monthly transfer" }

    Adds a contribution to the goal and updates current_amount.
    Automatically marks goal as complete if target is reached.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, goal_id):
        try:
            goal = SavingsGoal.objects.get(id=goal_id, user=request.user)
        except SavingsGoal.DoesNotExist:
            return Response(
                {"error": "Goal not found.", "code": "NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if goal.is_complete:
            return Response(
                {"error": "This goal is already complete.", "code": "GOAL_COMPLETE"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = GoalContributionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"error": "Invalid data.", "details": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        amount = serializer.validated_data["amount"]
        note = serializer.validated_data.get("note", "")

        # Create contribution record
        contribution = GoalContribution.objects.create(
            goal=goal,
            amount=amount,
            note=note,
        )

        # Update goal's current amount
        goal.current_amount += amount

        # Auto-complete if target reached
        milestone = None
        if goal.current_amount >= goal.target_amount:
            goal.current_amount = goal.target_amount
            goal.is_complete = True
            milestone = "complete"
        elif goal.progress_percent >= 75:
            milestone = "75_percent"
        elif goal.progress_percent >= 50:
            milestone = "50_percent"
        elif goal.progress_percent >= 25:
            milestone = "25_percent"

        goal.save(update_fields=["current_amount", "is_complete", "updated_at"])

        return Response({
            "message": f"Contribution of {goal.currency} {amount:,.0f} added successfully.",
            "contribution": GoalContributionSerializer(contribution).data,
            "goal": SavingsGoalSerializer(goal, context={"request": request}).data,
            "milestone": milestone,
        }, status=status.HTTP_201_CREATED)


class GoalContributionListView(APIView):
    """
    GET /api/savings/<id>/contributions/
    Lists all contributions for a specific goal.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, goal_id):
        try:
            goal = SavingsGoal.objects.get(id=goal_id, user=request.user)
        except SavingsGoal.DoesNotExist:
            return Response(
                {"error": "Goal not found.", "code": "NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )

        contributions = GoalContribution.objects.filter(
            goal=goal
        ).order_by("-created_at")

        serializer = GoalContributionSerializer(contributions, many=True)
        return Response({
            "contributions": serializer.data,
            "total_contributed": sum(c.amount for c in contributions),
            "count": contributions.count(),
        })