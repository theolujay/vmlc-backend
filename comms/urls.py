from django.urls import path

from .views import (
    BroadcastView,
    DatabaseBackupWebhookView,
    MarkAllNotificationsAsReadView,
    MarkNotificationAsReadView,
    NotificationHistory,
    SupportConversationDetailView,
    SupportConversationListView,
    SupportReplyView,
    PublicSupportRequestView,
)

app_name = "comms"

urlpatterns = [
    # Support & Conversations
    path("support-us/", PublicSupportRequestView.as_view(), name="support-us-inquiry"),
    path(
        "support/conversations/",
        SupportConversationListView.as_view(),
        name="support-conversations",
    ),
    path(
        "support/conversations/<int:id>/",
        SupportConversationDetailView.as_view(),
        name="support-conversation-detail",
    ),
    path(
        "support/conversations/<int:chat_thread_id>/reply/",
        SupportReplyView.as_view(),
        name="support-reply",
    ),
    # Broadcasts
    path("broadcasts/", BroadcastView.as_view(), name="broadcast-list-create"),
    path(
        "broadcasts/<int:broadcast_id>/",
        BroadcastView.as_view(),
        name="broadcast-detail",
    ),
    path(
        "webhooks/db-backup/",
        DatabaseBackupWebhookView.as_view(),
        name="db-backup-webhook",
    ),
    path(
        "notifications/",
        NotificationHistory.as_view(),
        name="notifications-history",
    ),
    path(
        "notifications/mark-all-as-read/",
        MarkAllNotificationsAsReadView.as_view(),
        name="mark-all-notifications-as-read",
    ),
    path(
        "notifications/<int:notification_id>/mark-as-read/",
        MarkNotificationAsReadView.as_view(),
        name="mark-notification-as-read",
    ),
]
