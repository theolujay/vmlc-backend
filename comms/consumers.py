import logging
import asyncio
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
        """Marks a notification as read in the database and invalidates cache."""
        user = self.scope["user"]
        try:
            notification = Notification.objects.get(
                id=notification_id,
                recipient=user,
                is_read=False
            )
            notification.is_read = True
            notification.save() # Triggers signals for invalidation
            return 1
        except Notification.DoesNotExist:
            return 0

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


class SupportChatConsumer(GenericAsyncAPIConsumer):
    """
    Handles real-time support chat, presence, and typing indicators.
    """

    async def connect(self):
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

        self.thread_id = self.scope["url_route"]["kwargs"].get("thread_id")
        if not self.thread_id:
            await self.close()
            return

        # Validate membership (Staff or Thread Owner)
        has_access = await self.check_thread_access(user, self.thread_id)
        if not has_access:
            await self.close(code=4003)
            return

        self.group_name = f"support_thread_{self.thread_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)

        # Presence Detection (Redis-Based)
        await self.set_presence(user.id, True)

        await self.accept()

        # Start presence refresh task
        self.presence_task = asyncio.create_task(self.refresh_presence_periodically(user.id))

    async def disconnect(self, close_code):
        user = self.scope.get("user")
        if user and user.is_authenticated:
            if hasattr(self, "group_name"):
                await self.channel_layer.group_discard(self.group_name, self.channel_name)

            # Stop presence refresh task
            if hasattr(self, "presence_task"):
                self.presence_task.cancel()

            # Clear presence
            await self.set_presence(user.id, False)

    async def receive_json(self, content, **kwargs):
        action = content.get("type")
        user = self.scope["user"]

        if action == "chat.typing":
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "chat.typing",
                    "user_id": str(user.id),
                    "is_typing": content.get("is_typing", False)
                }
            )

    async def chat_message(self, event):
        """Forward message to WebSocket."""
        await self.send_json(event)

    async def chat_typing(self, event):
        """Forward typing status to WebSocket."""
        # Don't send back to the user who is typing
        if event["user_id"] != str(self.scope["user"].id):
            await self.send_json(event)

    @database_sync_to_async
    def check_thread_access(self, user, thread_id):
        from .models import SupportChatThread
        from identity.models import Staff
        try:
            thread = SupportChatThread.objects.get(id=thread_id)

            # Staff check: Must be at least Moderator
            if hasattr(user, "staff_profile"):
                role = user.staff_profile.role
                role_levels = {
                    Staff.Roles.VOLUNTEER: 1,
                    Staff.Roles.SPONSOR: 2,
                    Staff.Roles.MODERATOR: 3,
                    Staff.Roles.ADMIN: 4,
                    Staff.Roles.MANAGER: 5,
                    Staff.Roles.SUPERADMIN: 6,
                }
                return role_levels.get(role, 0) >= role_levels.get(Staff.Roles.MODERATOR)

            # Candidate check: Must be the owner
            return hasattr(user, "candidate_profile") and thread.candidate_id == user.candidate_profile.pk
        except (SupportChatThread.DoesNotExist, AttributeError):
            return False

    async def set_presence(self, user_id, is_online):
        from django.core.cache import cache
        key = f"user_online_{user_id}"
        if is_online:
            cache.set(key, 1, timeout=60)
        else:
            cache.delete(key)

    async def refresh_presence_periodically(self, user_id):
        from django.core.cache import cache
        try:
            while True:
                await asyncio.sleep(30)
                cache.set(f"user_online_{user_id}", 1, timeout=60)
        except asyncio.CancelledError:
            pass
