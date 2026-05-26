"""
Management command to create system categories.
Run once after migrations:
  python manage.py seed_categories
"""

from django.core.management.base import BaseCommand
from transactions.models import Category


SYSTEM_CATEGORIES = [
    # Expenses
    {"name": "Food & Groceries",    "icon": "shopping-cart", "color": "#10B981", "type": "expense"},
    {"name": "Transport",           "icon": "car",           "color": "#3B82F6", "type": "expense"},
    {"name": "Housing & Rent",      "icon": "home",          "color": "#8B5CF6", "type": "expense"},
    {"name": "Utilities",           "icon": "zap",           "color": "#F59E0B", "type": "expense"},
    {"name": "Healthcare",          "icon": "heart",         "color": "#EF4444", "type": "expense"},
    {"name": "Entertainment",       "icon": "tv",            "color": "#EC4899", "type": "expense"},
    {"name": "Education",           "icon": "book",          "color": "#06B6D4", "type": "expense"},
    {"name": "Shopping",            "icon": "bag",           "color": "#F97316", "type": "expense"},
    {"name": "Insurance",           "icon": "shield",        "color": "#6366F1", "type": "expense"},
    {"name": "Loans & Debt",        "icon": "credit-card",   "color": "#DC2626", "type": "expense"},
    {"name": "Mobile Money",        "icon": "smartphone",    "color": "#0EA5E9", "type": "expense"},
    {"name": "Business Expenses",   "icon": "briefcase",     "color": "#78716C", "type": "expense"},
    {"name": "Travel",              "icon": "map",           "color": "#14B8A6", "type": "expense"},
    {"name": "Personal Care",       "icon": "user",          "color": "#A855F7", "type": "expense"},
    {"name": "Other Expenses",      "icon": "more-horizontal","color": "#6B7280","type": "expense"},

    # Income
    {"name": "Salary",              "icon": "dollar-sign",   "color": "#10B981", "type": "income"},
    {"name": "Business Income",     "icon": "trending-up",   "color": "#3B82F6", "type": "income"},
    {"name": "Freelance",           "icon": "code",          "color": "#8B5CF6", "type": "income"},
    {"name": "Investment Returns",  "icon": "bar-chart",     "color": "#F59E0B", "type": "income"},
    {"name": "Rental Income",       "icon": "home",          "color": "#06B6D4", "type": "income"},
    {"name": "Side Hustle",         "icon": "zap",           "color": "#EC4899", "type": "income"},
    {"name": "Other Income",        "icon": "plus-circle",   "color": "#6B7280", "type": "income"},

    # Transfers
    {"name": "Transfer",            "icon": "repeat",        "color": "#94A3B8", "type": "both"},
    {"name": "Savings",             "icon": "piggy-bank",    "color": "#10B981", "type": "both"},
]


class Command(BaseCommand):
    help = "Seed system categories used across all FlowIQ users"

    def handle(self, *args, **options):
        created = 0
        skipped = 0

        for cat_data in SYSTEM_CATEGORIES:
            _, was_created = Category.objects.get_or_create(
                name=cat_data["name"],
                is_system=True,
                defaults={
                    "icon": cat_data["icon"],
                    "color": cat_data["color"],
                    "type": cat_data["type"],
                    "user": None,
                },
            )
            if was_created:
                created += 1
            else:
                skipped += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Created {created} categories, skipped {skipped} existing."
            )
        )