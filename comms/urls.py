from django.urls import path

from .views import (
    BroadcastView,
    DatabaseBackupWebhookView,
    MarkAllNotificationsAsReadView,
    MarkNotificationAsReadView,
    NotificationHistory,
    StaffSupportThreadDetailView,
    StaffSupportThreadListView,
    SupportThreadMessageView,
    SupportThreadView,
    PublicSupportRequestView,
)

app_name = "comms"

urlpatterns = [
    # Support Chat
    path("support/thread/", SupportThreadView.as_view(), name="support-thread"),
    path(
        "support/thread/<uuid:thread_id>/message/",
        SupportThreadMessageView.as_view(),
        name="support-thread-message",
    ),
    path(
        "staff/support/threads/",
        StaffSupportThreadListView.as_view(),
        name="staff-support-threads",
    ),
    path(
        "staff/support/threads/<uuid:id>/",
        StaffSupportThreadDetailView.as_view(),
        name="staff-support-thread-detail",
    ),
    # Support & Conversations (Legacy/Old paths - maybe keep or remove?)
    path("support-us/", PublicSupportRequestView.as_view(), name="support-us-inquiry"),
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
