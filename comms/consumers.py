import logging
from channels.db import database_sync_to_async
from djangochannelsrestframework.generics import GenericAsyncAPIConsumer

from .models import Notification
from .serializers import NotificationSerializer


logger = logging.getLogger(__name__)


class NotificationConsumer(GenericAsyncAPIConsumer):

    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer

    @database_sync_to_async
    def get_user_profile(self, user):
        if hasattr(user, "candidate_profile"):
            return user.candidate_profile
        elif hasattr(user, "staff_profile"):
            return user.staff_profile
        return None

    async def connect(self):
        """
        Called when the websocket is trying to connect.
        If the user is not authenticated the connection will be rejected.
        """
        is_fully_authenticated = self.scope.get("fully_authenticated", False)

        if not is_fully_authenticated:
            api_key_ok = self.scope.get("api_key_authenticated", False)
            jwt_ok = self.scope.get("jwt_authenticated", False)

            if not api_key_ok and not jwt_ok:
                logger.warning(
                    "Connection rejected: Missing both API Key and JWT token"
                )
            elif not api_key_ok:
                logger.warning("Connection rejected: Invalid or missing API key")
            elif not jwt_ok:
                logger.warning("Connection rejected: Invalid or missing JWT token")
            await self.close(code=4003)
            return

        user = self.scope["user"]
        logger.info(f"Connecting user: {user}")

        if user.is_authenticated:
            profile = await self.get_user_profile(user)
            if profile:
                logger.info(f"WebSocket connected: {user.email}")
                # Subscribe the user to their unique notification group
                group_name = f"user__{user.pk}"
                await self.channel_layer.group_add(group_name, self.channel_name)
                logger.info(f"Subscribed to group: {group_name}")
                await self.accept()
            else:
                logger.warning(f"User {user.email} has no profile.")
                await self.close()
        else:
            logger.warning("User is not authenticated.")
            await self.close()

    async def disconnect(self, close_code):
        user = self.scope.get("user")
        if user and user.is_authenticated:
            # Unsubscribe from the group on disconnect
            group_name = f"user__{user.pk}"
            await self.channel_layer.group_discard(group_name, self.channel_name)
            logger.info(f"Unsubscribed from group: {group_name}")
        logger.info(
            f"WebSocket disconnected with code: {close_code} for anonymous user"
        )

    async def receive_json(self, content, **kwargs):
        """
        Handles incoming JSON messages from the client, routing them based on an 'action' key.
        """
        action = content.get("action")
        data = content.get("data")
        logger.info(
            f"Received action '{action}' from client {self.scope['user'].email}"
        )

        if action == "mark_as_read":
            await self.handle_mark_as_read(data)
        else:
            await self.send_error(f"Unknown action: {action}")

    async def handle_mark_as_read(self, data):
        """Handles the 'mark_as_read' action from the client."""
        notification_id = data.get("notification_id")
        if not notification_id:
            await self.send_error(
                "notification_id is required for 'mark_as_read' action."
            )
            return

        updated_count = await self.mark_notification_as_read(notification_id)

        if updated_count > 0:
            logger.info(
                f"Marked notification {notification_id} as read for user {self.scope['user'].pk}"
            )
        else:
            logger.warning(
                f"Could not find notification {notification_id} to mark as read for user {self.scope['user'].pk}"
            )

    @database_sync_to_async
    def mark_notification_as_read(self, notification_id):
        """Marks a notification as read in the database."""
        return Notification.objects.filter(
            id=notification_id, recipient=self.scope["user"]
        ).update(read=True)

    async def send_error(self, message):
        """Sends a standardized error message to the client."""
        await self.send_json({"type": "error", "message": message})

    async def notification_activity(self, message, **kwargs):
        """
        This method is called by the channel layer when a message is sent
        to a group this consumer is subscribed to. It simply forwards the
        message payload to the connected client.
        """
        await self.send_json(dict(message))
