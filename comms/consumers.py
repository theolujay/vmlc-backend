import logging
import asyncio
from djangochannelsrestframework.generics import GenericAsyncAPIConsumer

from .services.ws_notification import WSNotificationService
from .services.ws_helpdesk_dashboard import WSHelpdeskDashboardService
from .services.ws_helpdesk_thread import WSHelpdeskThreadService
from vmlc.utils.query_filters import ongoing_exam_exists
from channels.db import database_sync_to_async

logger = logging.getLogger(__name__)


class UnifiedConsumer(GenericAsyncAPIConsumer):
    """
    A single WebSocket consumer handling all real-time streams by delegating to services:
    - Notifications (Automatic)
    - Staff Helpdesk Dashboard (Automatic for Staff)
    - Specific Helpdesk Threads (On-demand subscription)
    """

    @classmethod
    async def encode_json(cls, content):
        import json
        from django.core.serializers.json import DjangoJSONEncoder

        return json.dumps(content, cls=DjangoJSONEncoder)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.subscribed_threads = set()
        self.is_staff = False
        self.user_group = None
        self.dashboard_group = None
        self.presence_task = None
        self.current_filters = {}
        self.current_request_id = None
        self.presence_set_name = "online_staff"  # Default

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

        await self.accept()
        logger.info(f"Unified WebSocket connected: {user.email}")

        # Send socket_id (channel_name) to the client
        await self.send_json({
            "type": "connection.established",
            "data": {
                "socket_id": self.channel_name
            }
        })

        # 1. Always subscribe to private notification group
        self.user_group = f"user__{user.pk}"
        await self.channel_layer.group_add(self.user_group, self.channel_name)

        # 2. Setup Helpdesk (Dashboard & Presence)
        self.is_staff = await WSHelpdeskDashboardService.check_staff_access(user)
        self.presence_set_name = await WSHelpdeskThreadService.get_user_type_set_name(
            user
        )

        if self.is_staff:
            self.dashboard_group = "staff_helpdesk_dashboard"
            await self.channel_layer.group_add(self.dashboard_group, self.channel_name)
            # Initialize dashboard state
            self.current_filters = {}
            await self.fetch_and_send_thread_list()

        # 3. Presence online
        await WSHelpdeskThreadService.set_presence(
            user.id, self.presence_set_name, True
        )
        self.presence_task = asyncio.create_task(
            self.refresh_presence_periodically(user.id)
        )

    async def disconnect(self, close_code):
        user = self.scope.get("user")
        if user and user.is_authenticated:
            # Leave notification group
            if self.user_group:
                await self.channel_layer.group_discard(
                    self.user_group, self.channel_name
                )

            # Leave staff dashboard group
            if self.dashboard_group:
                await self.channel_layer.group_discard(
                    self.dashboard_group, self.channel_name
                )

            # Leave all subscribed threads
            for thread_id in list(self.subscribed_threads):
                await self.channel_layer.group_discard(
                    f"helpdesk_thread_{thread_id}", self.channel_name
                )

            # Stop presence refresh task
            if self.presence_task:
                self.presence_task.cancel()

            # Clear presence
            await WSHelpdeskThreadService.set_presence(
                user.id, self.presence_set_name, False
            )

        user_email = user.email if user and user.is_authenticated else "Anonymous"
        logger.info(f"Unified WebSocket disconnected: {user_email}")

    async def receive_json(self, content, **kwargs):
        action = content.get("action")
        data = content.get("data", {})
        user = self.scope["user"]

        # --- Notification Actions ---
        if action == "mark_notification_as_read":
            notification_id = data.get("notification_id")
            if notification_id:
                await WSNotificationService.mark_as_read(user, notification_id)
            else:
                await self.send_error("notification_id is required")

        # --- Helpdesk Dashboard Actions ---
        elif action == "list_threads":
            if not self.is_staff:
                await self.send_error("Permission denied")
                return
            self.current_filters = data.get("filters", {})
            self.current_request_id = data.get("request_id")
            await self.fetch_and_send_thread_list()

        # --- Helpdesk Thread Actions ---
        elif action == "subscribe_thread":
            thread_id = data.get("thread_id")
            if await WSHelpdeskThreadService.check_access(
                user, thread_id, self.is_staff
            ):
                group = f"helpdesk_thread_{thread_id}"
                await self.channel_layer.group_add(group, self.channel_name)
                self.subscribed_threads.add(thread_id)
                logger.info(f"User {user.email} subscribed to thread {thread_id}")
            else:
                await self.send_error("Thread access denied")

        elif action == "unsubscribe_thread":
            thread_id = data.get("thread_id")
            if thread_id in self.subscribed_threads:
                await self.channel_layer.group_discard(
                    f"helpdesk_thread_{thread_id}", self.channel_name
                )
                self.subscribed_threads.remove(thread_id)

        elif action == "thread.typing":
            thread_id = data.get("thread_id")
            if thread_id in self.subscribed_threads:
                await self.channel_layer.group_send(
                    f"helpdesk_thread_{thread_id}",
                    {
                        "type": "helpdesk.thread.typing",
                        "thread_id": thread_id,
                        "user_id": str(user.id),
                        "is_typing": data.get("is_typing", False),
                    },
                )
        elif action == "exam.unlock_request":
            if not self.is_staff:
                await self.send_error("Permission denied")
                return

            candidate_id = data.get("candidate_id")
            exam_id = data.get("exam_id")
            target_socket_id = data.get("socket_id")

            if not candidate_id or not exam_id or not target_socket_id:
                await self.send_error("candidate_id, exam_id, and socket_id are required")
                return

            # Update database state (as an audit trail and for verification gate)
            result = await self.persist_exam_unlock(candidate_id, exam_id, user)
            
            if result == "success":
                # Send specifically to the device that generated the QR — prevents
                # an imposter from unlocking the exam on a different machine
                await self.channel_layer.send(
                    target_socket_id,
                    {
                        "type": "exam.unlocked",
                        "data": {
                            "exam_id": exam_id,
                            "unlocked_by_name": f"{user.first_name} {user.last_name}".strip() or user.email,
                            "timestamp": str(asyncio.get_event_loop().time())
                        },
                    }
                )
            elif result == "not_final":
                await self.send_error("This exam is not a final exam and cannot be unlocked via QR.")
            else:
                await self.send_error("Failed to unlock exam session. Access record not found.")

        else:
            await self.send_error(f"Unknown action: {action}")

    # ============================================================
    # Group Message Handlers
    # ============================================================

    async def exam_unlocked(self, event):
        """Forwards exam unlock events to the candidate."""
        await self.send_json({
            "type": "exam.unlocked",
            "data": event.get("data", {})
        })

    async def notification_activity(self, event):
        """Forwards notification events to the client."""
        # Normalize to use 'data' key for consistency
        payload = {"type": "notification_activity", "data": event.get("message", {})}
        await self.send_json(payload)

    async def helpdesk_update(self, event):
        """Forward global stats update and refresh staff list if needed."""
        # Normalize: already usually {type, data}, but ensure it's clean
        payload = {"type": event["type"], "data": event.get("data", {})}
        await self.send_json(payload)

        if self.is_staff and payload["data"].get("refresh_threads"):
            await self.fetch_and_send_thread_list()

    async def helpdesk_thread(self, event):
        """Forward thread updates (messages/metadata) to participants."""
        payload = {"type": event["type"], "data": event.get("data", {})}
        await self.send_json(payload)

    async def helpdesk_thread_typing(self, event):
        """Forward typing status to other participants."""
        if event["user_id"] != str(self.scope["user"].id):
            # Wrap in 'data' object to match frontend expectations
            payload = {
                "type": event["type"],
                "data": {
                    "thread_id": event["thread_id"],
                    "user_id": event["user_id"],
                    "is_typing": event["is_typing"],
                },
            }
            await self.send_json(payload)

    # ============================================================
    # Helpers
    # ============================================================

    async def fetch_and_send_thread_list(self):
        filters = dict(self.current_filters)
        if "status" not in filters or not filters["status"]:
            has_ongoing_exam = await database_sync_to_async(ongoing_exam_exists)()
            filters["status"] = "default" if has_ongoing_exam else "all"
        data = await WSHelpdeskDashboardService.get_thread_list(filters)
        data["filters"] = filters
        if hasattr(self, "current_request_id") and self.current_request_id is not None:
            data["request_id"] = self.current_request_id
        await self.send_json({"type": "helpdesk.list", "data": data})

    async def refresh_presence_periodically(self, user_id):
        try:
            while True:
                await asyncio.sleep(30)
                await WSHelpdeskThreadService.refresh_presence(
                    user_id, self.presence_set_name
                )
        except asyncio.CancelledError:
            pass

    @database_sync_to_async
    def persist_exam_unlock(self, candidate_id, exam_id, staff_user):
        """Persists the unlock status in the database.
        
        Returns:
            "success" - exam unlocked successfully
            "not_final" - exam is not a final exam
            False - access record not found
        """
        from vmlc.models import ExamAccess, Exam
        from identity.models import Staff

        try:
            access = ExamAccess.objects.get(candidate_id=candidate_id, exam_id=exam_id)

            # Only final exams can be unlocked via QR
            exam = (
                Exam.objects.select_related(
                    "competition_slot__competition_stage"
                )
                .get(pk=exam_id)
            )
            if exam.stage != "final":
                return "not_final"

            access.is_unlocked = True

            # Get the staff record
            try:
                staff = Staff.objects.get(user=staff_user)
                access.unlocked_by = staff
            except Staff.DoesNotExist:
                pass

            access.save()
            return "success"
        except ExamAccess.DoesNotExist:
            return False

    async def send_error(self, message):
        await self.send_json({"type": "error", "message": message})
