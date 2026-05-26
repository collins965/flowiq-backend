"""
FlowIQ — AI Chat Views
Handles all FlowAI conversation endpoints.

Endpoints (wire in ai_chat/urls.py):
  POST   /api/v1/ai/chat/                          → ChatView
  GET    /api/v1/ai/conversations/                 → ConversationListView
  DELETE /api/v1/ai/conversations/clear/           → ClearAllConversationsView
  GET    /api/v1/ai/conversations/<uuid>/          → ConversationDetailView
  DELETE /api/v1/ai/conversations/<uuid>/          → ConversationDetailView
  PATCH  /api/v1/ai/conversations/<uuid>/title/    → RenameConversationView
  GET    /api/v1/ai/suggestions/                   → SuggestionsView
  GET    /api/v1/ai/usage/                         → UsageView
"""

import json
import logging
import uuid
from typing import Optional, Tuple

import anthropic

from django.conf import settings
from django.http import StreamingHttpResponse
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from transactions.models import Transaction
from budgets.models import Budget
from ai_chat.models import AIConversation

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

FREE_TIER_MONTHLY_LIMIT = 5
MAX_MESSAGES_PER_CONVERSATION = 100
AI_MODEL = "claude-sonnet-4-20250514"
AI_MAX_TOKENS = 1500  # increased — 1024 cuts off longer responses


# ─────────────────────────────────────────────────────────────────────────────
# Financial context builder
# ─────────────────────────────────────────────────────────────────────────────

def get_user_financial_context(user) -> dict:
    """
    Build a rich financial context snapshot injected into every AI system prompt.
    Pulls from transactions, budgets, and the user's profile.
    """
    # --- Transactions ---
    transactions = (
        Transaction.objects
        .filter(user_id=user.id)
        .order_by("-date")
        .select_related("category")[:50]
    )

    if transactions.exists():
        recent_lines = [
            "{merchant}: {currency} {amount:,.0f} ({category})".format(
                merchant=t.merchant or t.description or "Unknown",
                currency="KES",
                amount=abs(float(t.amount)),
                category=t.category.name if t.category else "uncategorized",
            )
            for t in transactions[:10]
        ]
        tx_summary = (
            f"{transactions.count()} transactions on record. "
            f"Most recent 10: {'; '.join(recent_lines)}"
        )

        # Aggregate totals for the current calendar month
        now = timezone.now()
        month_txs = [
            t for t in transactions
            if t.date.month == now.month and t.date.year == now.year
        ]
        month_income = sum(
            float(t.amount) for t in month_txs if float(t.amount) > 0
        )
        month_expenses = sum(
            abs(float(t.amount)) for t in month_txs if float(t.amount) < 0
        )
        tx_summary += (
            f" | This month: income KES {month_income:,.0f}, "
            f"expenses KES {month_expenses:,.0f}"
        )
    else:
        tx_summary = "No transactions recorded yet."

    # --- Budgets ---
    budgets = Budget.objects.filter(user_id=user.id).select_related("category")

    if budgets.exists():
        budget_lines = [
            "{cat}: KES {amount:,.0f}/month".format(
                cat=b.category.name if b.category else "General",
                amount=float(b.amount),
            )
            for b in budgets
        ]
        budget_summary = "Budgets: " + "; ".join(budget_lines)
    else:
        budget_summary = "No budgets configured yet."

    # --- Profile ---
    profile = getattr(user, "profile", None)
    country_code = getattr(profile, "country_code", "KE")
    currency = getattr(profile, "currency_code", "KES")
    employment_type = getattr(profile, "employment_type", "employed")

    country_names = {
        "KE": "Kenya",
        "UG": "Uganda",
        "TZ": "Tanzania",
        "ZA": "South Africa",
        "NG": "Nigeria",
        "GH": "Ghana",
        "US": "United States",
        "GB": "United Kingdom",
    }
    country_name = country_names.get(country_code, country_code)

    return {
        "tx_summary": tx_summary,
        "budget_summary": budget_summary,
        "currency": currency,
        "country": country_name,
        "country_code": country_code,
        "employment_type": employment_type,
    }


# ─────────────────────────────────────────────────────────────────────────────
# System prompt builder
# ─────────────────────────────────────────────────────────────────────────────

def build_system_prompt(context: dict, user_name: str = "there") -> str:
    """
    Build a rich, context-aware system prompt for FlowAI.
    Injected on every API call — never shown to the user.
    """
    employment_notes = {
        "employed": "The user has salaried employment income.",
        "self_employed": "The user is self-employed or runs their own business.",
        "both": (
            "The user has BOTH employment income and business/side hustle income. "
            "When discussing tax, account for both income streams."
        ),
    }
    employment_note = employment_notes.get(
        context.get("employment_type", "employed"), ""
    )

    kenya_tax_note = ""
    if context.get("country_code") == "KE":
        kenya_tax_note = """
KENYA TAX KNOWLEDGE (KRA 2024/2025):
- PAYE bands: 0-24,000@10%, 24,001-32,333@25%, 32,334-500,000@30%, 500,001-800,000@32.5%, 800,001+@35%
- Personal relief: KES 2,400/month
- NHIF: tiered KES 150-1,700 based on gross salary
- NSSF: Tier I 6% up to KES 7,000 (max KES 420), Tier II 6% of 7,001-36,000 (max KES 1,740)
- Housing Levy: 1.5% of gross salary
- Turnover Tax: 1.5% if annual revenue < KES 25M (self-employed)
- VAT: 16% standard (registration required if supplies > KES 5M/year)
"""

    return f"""You are FlowAI, the intelligent personal finance assistant inside FlowIQ.

USER: {user_name} | LOCATION: {context['country']} | CURRENCY: {context['currency']}
{employment_note}

━━━ THEIR CURRENT FINANCIAL SNAPSHOT ━━━
{context['tx_summary']}
{context['budget_summary']}
{kenya_tax_note}
━━━ YOUR BEHAVIOUR RULES ━━━
- Be warm, sharp, and immediately useful — like a financially savvy friend
- Give SPECIFIC numbers when you have data. Never give vague advice like "spend less"
- Format all amounts as: {context['currency']} XX,XXX  (e.g. KES 45,000 or USD 1,200)
- Use markdown: **bold** for key figures, bullet points for action steps, tables for comparisons
- For Kenyan tax questions: use the KRA rates above — be precise
- For fraud questions: reference the Computer Misuse & Cybercrimes Act 2018 where relevant
- End EVERY response with: **Next step:** one concrete action the user can take TODAY
- If you lack data to answer precisely: say so clearly and ask for the one missing piece
- NEVER invent transaction figures, balances, or amounts not in the snapshot above
- You CAN answer general finance questions (investing, insurance, salary negotiation) even without user data
- Keep responses focused — no padding, no filler sentences"""


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_anthropic_client() -> anthropic.Anthropic:
    """Return a configured Anthropic client. Raises clearly if key is missing."""
    api_key = getattr(settings, "ANTHROPIC_API_KEY", None)
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY is not configured. "
            "Add ANTHROPIC_API_KEY=sk-ant-... to your .env file and settings.py."
        )
    return anthropic.Anthropic(api_key=api_key)


def check_free_tier_limit(user) -> Tuple[bool, int]:
    """
    Check if the user is allowed to make an AI query.
    Returns (is_allowed, queries_remaining).
    Pro and Business users always get (True, 999).
    """
    profile = getattr(user, "profile", None)
    if profile is None:
        return True, 999

    plan = getattr(profile, "plan", "free")
    if plan in ("pro", "business"):
        return True, 999

    # --- Monthly reset check ---
    # If the counter was last reset in a previous month, reset it now
    reset_at = getattr(profile, "ai_queries_reset_at", None)
    now = timezone.now()
    if reset_at is None or reset_at.month != now.month or reset_at.year != now.year:
        profile.ai_queries_this_month = 0
        profile.ai_queries_reset_at = now
        profile.save(update_fields=["ai_queries_this_month", "ai_queries_reset_at"])

    queries_used = getattr(profile, "ai_queries_this_month", 0)
    remaining = max(0, FREE_TIER_MONTHLY_LIMIT - queries_used)
    return remaining > 0, remaining


def increment_query_count(user) -> None:
    """Increment monthly AI query counter atomically — no race condition."""
    profile = getattr(user, "profile", None)
    if profile is None:
        return
    if getattr(profile, "plan", "free") == "free":
        from django.db.models import F
        from core.models import Profile
        Profile.objects.filter(id=profile.id).update(
            ai_queries_this_month=F("ai_queries_this_month") + 1
        )

def save_conversation(
    user,
    conversation_id: Optional[str],
    messages: list,
    reply: str,
) -> str:
    """
    Persist the exchange to the database.
    - Creates a new AIConversation if conversation_id is None or not found.
    - Auto-generates a title from the first user message.
    - Caps stored messages at MAX_MESSAGES_PER_CONVERSATION.
    Returns the conversation UUID as a string.
    """
    # Derive title from first user message in this exchange
    first_user_msg = next(
        (m.get("content", "") for m in messages if m.get("role") == "user"),
        "",
    )
    if isinstance(first_user_msg, list):
        # Handle multimodal content (list of content blocks)
        first_user_msg = next(
            (block.get("text", "") for block in first_user_msg if block.get("type") == "text"),
            "",
        )
    auto_title = (
        (first_user_msg[:57] + "...") if len(first_user_msg) > 60 else first_user_msg
    ) or "New conversation"

    # Find existing conversation or create new one
    conv = None
    if conversation_id:
        try:
            conv = AIConversation.objects.get(
                id=conversation_id,
                user_id=user.id,
            )
        except (AIConversation.DoesNotExist, Exception):
            conv = None

    if conv is None:
        conv = AIConversation.objects.create(
            user_id=user.id,
            title=auto_title,
            messages=[],
        )

    # Merge incoming messages + new assistant reply
    stored = list(conv.messages or [])
    stored.extend(messages)
    stored.append({
        "role": "assistant",
        "content": reply,
        "timestamp": timezone.now().isoformat(),
    })

    # Cap to prevent unbounded growth
    conv.messages = stored[-MAX_MESSAGES_PER_CONVERSATION:]
    conv.updated_at = timezone.now()

    # Update title only if this is a brand new conversation (no prior messages)
    if len(stored) <= len(messages) + 1:
        conv.title = auto_title

    conv.save(update_fields=["messages", "updated_at", "title"])
    return str(conv.id)


def sanitize_messages(messages: list) -> list:
    """
    Strip any keys the Anthropic API doesn't accept (e.g. 'timestamp')
    and ensure content is a plain string or valid content block list.
    """
    clean = []
    for msg in messages:
        content = msg.get("content", "")
        # If content is a list of blocks (multimodal), pass as-is
        # If it's anything else, cast to string
        if not isinstance(content, (str, list)):
            content = str(content)
        clean.append({"role": msg["role"], "content": content})
    return clean


# ─────────────────────────────────────────────────────────────────────────────
# Views
# ─────────────────────────────────────────────────────────────────────────────

class ChatView(APIView):
    """
    POST /api/v1/ai/chat/

    Body:
      messages        list  required  [{role: "user"|"assistant", content: str}]
      stream          bool  optional  default true
      conversation_id str   optional  UUID of existing conversation to continue
      user_name       str   optional  display name override
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        messages = request.data.get("messages", [])
        stream = request.data.get("stream", True)
        conversation_id = request.data.get("conversation_id") or None
        user_name = (
            request.data.get("user_name")
            or request.user.get_full_name()
            or request.user.email.split("@")[0]
            or "there"
        )

        # ── Input validation ──────────────────────────────────────────────
        if not messages:
            return Response(
                {"error": "messages is required and cannot be empty.", "code": "NO_MESSAGES"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not isinstance(messages, list):
            return Response(
                {"error": "messages must be an array.", "code": "INVALID_FORMAT"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        for i, msg in enumerate(messages):
            if not isinstance(msg, dict):
                return Response(
                    {"error": f"messages[{i}] must be an object.", "code": "INVALID_MESSAGE"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if "role" not in msg or "content" not in msg:
                return Response(
                    {"error": f"messages[{i}] must have 'role' and 'content'.", "code": "INVALID_MESSAGE"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if msg["role"] not in ("user", "assistant"):
                return Response(
                    {
                        "error": f"messages[{i}].role must be 'user' or 'assistant', got '{msg['role']}'.",
                        "code": "INVALID_ROLE",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # The last message must be from the user
        if messages[-1].get("role") != "user":
            return Response(
                {"error": "The last message must have role 'user'.", "code": "INVALID_LAST_MESSAGE"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Plan limit check ──────────────────────────────────────────────
        allowed, remaining = check_free_tier_limit(request.user)
        if not allowed:
            return Response(
                {
                    "error": (
                        f"You've used all {FREE_TIER_MONTHLY_LIMIT} free AI queries for this month. "
                        "Upgrade to Pro for unlimited access."
                    ),
                    "code": "LIMIT_REACHED",
                    "upgrade_required": True,
                    "queries_remaining": 0,
                    "limit": FREE_TIER_MONTHLY_LIMIT,
                },
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        # ── Build AI context ──────────────────────────────────────────────
        try:
            context = get_user_financial_context(request.user)
            system_prompt = build_system_prompt(context, user_name)
            client = get_anthropic_client()
        except ValueError as exc:
            logger.error("FlowAI config error for user %s: %s", request.user.id, exc)
            return Response(
                {"error": str(exc), "code": "CONFIG_ERROR"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        clean_messages = sanitize_messages(messages)

        # ── Dispatch ──────────────────────────────────────────────────────
        if stream:
            return self._stream_response(
                client, system_prompt, clean_messages, messages,
                request.user, conversation_id, remaining,
            )
        return self._sync_response(
            client, system_prompt, clean_messages, messages,
            request.user, conversation_id, remaining,
        )

    # ── Streaming path ────────────────────────────────────────────────────

    def _stream_response(
        self, client, system_prompt, clean_messages, raw_messages,
        user, conversation_id, queries_remaining,
    ):
        collected_reply: list = []
        user_id_for_log = user.id  # capture before generator runs in thread

        def event_stream():
            try:
                with client.messages.stream(
                    model=AI_MODEL,
                    max_tokens=AI_MAX_TOKENS,
                    system=system_prompt,
                    messages=clean_messages,
                ) as stream_ctx:
                    for text in stream_ctx.text_stream:
                        collected_reply.append(text)
                        yield f"data: {json.dumps({'text': text})}\n\n"

                # Stream complete — save and notify
                full_reply = "".join(collected_reply)
                conv_id = save_conversation(user, conversation_id, raw_messages, full_reply)
                increment_query_count(user)

                yield f"data: {json.dumps({'done': True, 'conversation_id': conv_id, 'queries_remaining': max(0, queries_remaining - 1)})}\n\n"

            except anthropic.AuthenticationError:
                logger.error("Anthropic auth failed — check ANTHROPIC_API_KEY (user: %s)", user_id_for_log)
                yield f"data: {json.dumps({'error': 'AI authentication failed. Contact support.', 'code': 'AUTH_ERROR'})}\n\n"

            except anthropic.RateLimitError:
                logger.warning("Anthropic rate limit hit (user: %s)", user_id_for_log)
                yield f"data: {json.dumps({'error': 'FlowAI is busy right now. Please try again in a moment.', 'code': 'RATE_LIMIT'})}\n\n"

            except anthropic.BadRequestError as exc:
                logger.warning("Anthropic bad request (user: %s): %s", user_id_for_log, exc)
                yield f"data: {json.dumps({'error': 'Your message could not be processed. Please rephrase and try again.', 'code': 'BAD_REQUEST'})}\n\n"

            except anthropic.APIError as exc:
                logger.error("Anthropic API error (user: %s): %s", user_id_for_log, exc)
                yield f"data: {json.dumps({'error': 'FlowAI is temporarily unavailable. Please try again shortly.', 'code': 'API_ERROR'})}\n\n"

            except Exception as exc:
                logger.exception("Unexpected AI stream error (user: %s): %s", user_id_for_log, exc)
                yield f"data: {json.dumps({'error': 'An unexpected error occurred.', 'code': 'UNKNOWN_ERROR'})}\n\n"

        response = StreamingHttpResponse(
            event_stream(),
            content_type="text/event-stream; charset=utf-8",
        )
        response["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response["X-Accel-Buffering"] = "no"
        response["Connection"] = "keep-alive"
        return response

    # ── Non-streaming path ────────────────────────────────────────────────

    def _sync_response(
        self, client, system_prompt, clean_messages, raw_messages,
        user, conversation_id, queries_remaining,
    ):
        try:
            api_response = client.messages.create(
                model=AI_MODEL,
                max_tokens=AI_MAX_TOKENS,
                system=system_prompt,
                messages=clean_messages,
            )
        except anthropic.AuthenticationError:
            logger.error("Anthropic auth failed — check ANTHROPIC_API_KEY (user: %s)", user.id)
            return Response(
                {"error": "AI authentication failed. Contact support.", "code": "AUTH_ERROR"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except anthropic.RateLimitError:
            return Response(
                {"error": "FlowAI is busy right now. Please try again in a moment.", "code": "RATE_LIMIT"},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        except anthropic.BadRequestError as exc:
            logger.warning("Anthropic bad request (user: %s): %s", user.id, exc)
            return Response(
                {"error": "Your message could not be processed. Please rephrase and try again.", "code": "BAD_REQUEST"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except anthropic.APIError as exc:
            logger.error("Anthropic API error (user: %s): %s", user.id, exc)
            return Response(
                {"error": "FlowAI is temporarily unavailable.", "code": "API_ERROR"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        reply = api_response.content[0].text
        conv_id = save_conversation(user, conversation_id, raw_messages, reply)
        increment_query_count(user)

        return Response({
            "reply": reply,
            "conversation_id": conv_id,
            "model": AI_MODEL,
            "queries_remaining": max(0, queries_remaining - 1),
        }, status=status.HTTP_200_OK)


# ─────────────────────────────────────────────────────────────────────────────

class ConversationListView(APIView):
    """
    GET /api/v1/ai/conversations/
    Returns paginated list of conversations for the current user.
    Query params: page (default 1), page_size (default 20, max 50)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        page = max(1, int(request.query_params.get("page", 1)))
        page_size = min(50, max(1, int(request.query_params.get("page_size", 20))))
        offset = (page - 1) * page_size

        qs = (
            AIConversation.objects
            .filter(user_id=request.user.id)
            .order_by("-updated_at")
        )

        total = qs.count()
        conversations = list(
            qs.values("id", "title", "created_at", "updated_at")[offset: offset + page_size]
        )

        # Add message count and last message preview to each record
        for conv_data in conversations:
            try:
                conv_obj = AIConversation.objects.get(id=conv_data["id"])
                msgs = conv_obj.messages or []
                conv_data["message_count"] = len(msgs)
                # Preview: first 80 chars of the last user message
                last_user = next(
                    (m.get("content", "") for m in reversed(msgs) if m.get("role") == "user"),
                    "",
                )
                if isinstance(last_user, list):
                    last_user = next(
                        (b.get("text", "") for b in last_user if b.get("type") == "text"), ""
                    )
                conv_data["preview"] = (last_user[:80] + "...") if len(last_user) > 80 else last_user
            except AIConversation.DoesNotExist:
                conv_data["message_count"] = 0
                conv_data["preview"] = ""

        return Response({
            "conversations": conversations,
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_next": offset + page_size < total,
        })


# ─────────────────────────────────────────────────────────────────────────────

class ConversationDetailView(APIView):
    """
    GET    /api/v1/ai/conversations/<uuid>/  → retrieve full conversation
    DELETE /api/v1/ai/conversations/<uuid>/  → delete conversation
    """
    permission_classes = [IsAuthenticated]

    def _get_or_404(self, conversation_id, user_id):
        try:
            return AIConversation.objects.get(id=conversation_id, user_id=user_id)
        except AIConversation.DoesNotExist:
            return None

    def get(self, request, conversation_id):
        conv = self._get_or_404(conversation_id, request.user.id)
        if conv is None:
            return Response(
                {"error": "Conversation not found.", "code": "NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({
            "id": str(conv.id),
            "title": conv.title,
            "messages": conv.messages,
            "message_count": len(conv.messages or []),
            "created_at": conv.created_at,
            "updated_at": conv.updated_at,
        })

    def delete(self, request, conversation_id):
        deleted, _ = AIConversation.objects.filter(
            id=conversation_id,
            user_id=request.user.id,
        ).delete()
        if deleted:
            return Response({"message": "Conversation deleted."}, status=status.HTTP_200_OK)
        return Response(
            {"error": "Conversation not found.", "code": "NOT_FOUND"},
            status=status.HTTP_404_NOT_FOUND,
        )


# ─────────────────────────────────────────────────────────────────────────────

class RenameConversationView(APIView):
    """
    PATCH /api/v1/ai/conversations/<uuid>/title/
    Body: { "title": "New name" }
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, conversation_id):
        new_title = (request.data.get("title") or "").strip()
        if not new_title:
            return Response(
                {"error": "title is required.", "code": "MISSING_TITLE"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(new_title) > 200:
            return Response(
                {"error": "title must be 200 characters or fewer.", "code": "TITLE_TOO_LONG"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        updated = AIConversation.objects.filter(
            id=conversation_id,
            user_id=request.user.id,
        ).update(title=new_title, updated_at=timezone.now())

        if updated:
            return Response({"message": "Title updated.", "title": new_title})
        return Response(
            {"error": "Conversation not found.", "code": "NOT_FOUND"},
            status=status.HTTP_404_NOT_FOUND,
        )


# ─────────────────────────────────────────────────────────────────────────────

class ClearAllConversationsView(APIView):
    """
    DELETE /api/v1/ai/conversations/clear/
    Deletes ALL conversations for the current user.
    """
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        count, _ = AIConversation.objects.filter(user_id=request.user.id).delete()
        return Response({"message": f"{count} conversation(s) deleted."})


# ─────────────────────────────────────────────────────────────────────────────

class SuggestionsView(APIView):
    """
    GET /api/v1/ai/suggestions/
    Returns context-aware prompt suggestions for the AI chat empty state.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = getattr(request.user, "profile", None)
        country_code = getattr(profile, "country_code", "KE")
        employment_type = getattr(profile, "employment_type", "employed")

        has_transactions = Transaction.objects.filter(user_id=request.user.id).exists()
        has_budgets = Budget.objects.filter(user_id=request.user.id).exists()

        suggestions = []

        if has_transactions:
            suggestions += [
                "Analyze my spending patterns from last month",
                "Which category am I overspending in the most?",
                "What are my top 5 merchants by total spend?",
            ]
        else:
            suggestions += [
                "How do I get started with budgeting?",
                "What should my emergency fund target be?",
            ]

        if has_budgets:
            suggestions.append("Am I on track with my budgets this month?")
        else:
            suggestions.append("Help me set up a realistic monthly budget")

        if employment_type in ("self_employed", "both"):
            suggestions.append("What business expenses can I deduct for tax in Kenya?")
            suggestions.append("Explain Turnover Tax vs income tax for my business")
        else:
            suggestions.append("Break down my PAYE deductions for this month")

        if country_code == "KE":
            suggestions += [
                "How does Fuliza interest actually work?",
                "What's the best money market fund in Kenya right now?",
            ]

        suggestions.append("Give me 5 ways to increase my savings rate this month")

        return Response({"suggestions": suggestions[:8]})


# ─────────────────────────────────────────────────────────────────────────────

class UsageView(APIView):
    """
    GET /api/v1/ai/usage/
    Returns the current user's AI query usage for this month.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = getattr(request.user, "profile", None)
        if profile is None:
            return Response({"queries_used": 0, "limit": FREE_TIER_MONTHLY_LIMIT, "plan": "free"})

        plan = getattr(profile, "plan", "free")

        if plan in ("pro", "business"):
            return Response({
                "queries_used": getattr(profile, "ai_queries_this_month", 0),
                "limit": None,
                "unlimited": True,
                "plan": plan,
            })

        queries_used = getattr(profile, "ai_queries_this_month", 0)
        return Response({
            "queries_used": queries_used,
            "limit": FREE_TIER_MONTHLY_LIMIT,
            "queries_remaining": max(0, FREE_TIER_MONTHLY_LIMIT - queries_used),
            "unlimited": False,
            "plan": plan,
        })