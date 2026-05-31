from django.urls import path
from .views import (
    SavingsGoalListView,
    SavingsGoalDetailView,
    GoalContributeView,
    GoalContributionListView,
)

urlpatterns = [
    path("",                                    SavingsGoalListView.as_view(),      name="savings-list"),
    path("<uuid:goal_id>/",                     SavingsGoalDetailView.as_view(),    name="savings-detail"),
    path("<uuid:goal_id>/contribute/",          GoalContributeView.as_view(),       name="savings-contribute"),
    path("<uuid:goal_id>/contributions/",       GoalContributionListView.as_view(), name="savings-contributions"),
]