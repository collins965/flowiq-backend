from django.urls import path
from .views import (
    ChatView,
    ConversationListView,
    ConversationDetailView,
    RenameConversationView,
    ClearAllConversationsView,
    SuggestionsView,
    UsageView,
)

urlpatterns = [
    # Core chat
    path("chat/",                                       ChatView.as_view(),                 name="ai-chat"),

    # Conversation management
    path("conversations/",                              ConversationListView.as_view(),      name="ai-conversations"),
    path("conversations/clear/",                        ClearAllConversationsView.as_view(), name="ai-conversations-clear"),
    path("conversations/<uuid:conversation_id>/",       ConversationDetailView.as_view(),    name="ai-conversation-detail"),
    path("conversations/<uuid:conversation_id>/title/", RenameConversationView.as_view(),    name="ai-conversation-rename"),

    # Utility
    path("suggestions/",                                SuggestionsView.as_view(),           name="ai-suggestions"),
    path("usage/",                                      UsageView.as_view(),                 name="ai-usage"),
]