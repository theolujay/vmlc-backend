import logging

from channels.db import database_sync_to_async
from comms.models import Notification

logger = logging.getLogger(__name__)

class WSNotificationService:
    @staticmethod
    @database_sync_to_async
    def mark_as_read(user, notification_id):
        """Marks a notification as read for the given user."""
        try:
            notification = Notification.objects.get(
                id=notification_id, recipient=user, is_read=False
            )
            notification.is_read = True
            notification.save()
            return True
        except Notification.DoesNotExist:
            return False
