from django.urls import path

from .views import BroadcastView, DatabaseBackupWebhookView

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
]
