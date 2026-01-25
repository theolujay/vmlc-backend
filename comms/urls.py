from django.urls import path

from .views import (
    BroadcastView,
    DatabaseBackupWebhookView,
    MarkAllNotificationsAsReadView,
    MarkNotificationAsReadView,
    NotificationHistory,
)

app_name = "comms"

urlpatterns = [
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
