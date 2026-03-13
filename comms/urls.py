from django.urls import path

from .views import (
    BroadcastView,
    DatabaseBackupWebhookView,
    MarkAllNotificationsAsReadView,
    MarkNotificationAsReadView,
    NotificationHistory,
    StaffHelpdeskThreadDetailView,
    StaffHelpdeskThreadActionView,
    StaffHelpdeskThreadListView,
    HelpdeskThreadMessageView,
    HelpdeskThreadView,
    PublicSupportRequestView,
)

app_name = "comms"

urlpatterns = [
    # Helpdesk
    path("helpdesk/thread/", HelpdeskThreadView.as_view(), name="helpdesk-thread"),
    path(
        "helpdesk/thread/<uuid:thread_id>/message/",
        HelpdeskThreadMessageView.as_view(),
        name="helpdesk-thread-message",
    ),
    path(
        "staff/helpdesk/threads/",
        StaffHelpdeskThreadListView.as_view(),
        name="staff-helpdesk-threads",
    ),
    path(
        "staff/helpdesk/threads/<uuid:id>/",
        StaffHelpdeskThreadDetailView.as_view(),
        name="staff-helpdesk-thread-detail",
    ),
    path(
        "staff/helpdesk/threads/<uuid:id>/action",
        StaffHelpdeskThreadActionView.as_view(),
        name="staff-helpdesk-thread-action",
    ),
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
