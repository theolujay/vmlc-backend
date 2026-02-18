import logging
from datetime import datetime

from django.core.cache import cache
from django.db import models, transaction
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import mixins, status
from rest_framework.generics import (
    GenericAPIView,
    ListAPIView,
    CreateAPIView,
    RetrieveAPIView,
)
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny

from comms.models import (
    BackupLog,
    Broadcast,
    BroadcastLog,
    Notification,
    SupportChatThread,
    MessageRead,
    ThreadMessage,
)
from comms.serializers import (
    BroadcastDetailSerializer,
    BroadcastListSerializer,
    NotificationSerializer,
    PublicSupportRequestSerializer,
    SupportChatThreadDetailSerializer,
    SupportChatThreadListSerializer,
    ThreadMessageSerializer,
)
from comms.tasks import send_broadcast_task
from identity.permissions import (
    HasXAPIKey,
    AuthenticatedUser,
    CandidatePermissions,
    ActiveManagerPermissions,
    ActiveModeratorPermissions,
)
from vmlc.utils.helpers import sanitize_data
from vmlc.utils.query_filters import filter_broadcasts
from vmlc.v2.utils import CacheKeys

logger = logging.getLogger(__name__)


class ListCreateRetrieveAPIView(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    GenericAPIView,
):
    """
    A custom view that combines list, create, and retrieve functionality.

    This view handles:
    - GET (no ID): List all items
    - GET (with ID): Retrieve specific item
    - POST: Create new item
    """

    def get(self, request, *args, **kwargs):
        """
        Handle GET requests - either list all or retrieve specific item.

        The key here is checking if we have a lookup parameter (like broadcast_id).
        If we do, it's a retrieve operation. If not, it's a list operation.
        """
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        if lookup_url_kwarg in kwargs:
            return self.retrieve(request, *args, **kwargs)
        else:
            return self.list(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        """Handle POST requests for creating new items."""
        return self.create(request, *args, **kwargs)


class BroadcastView(ListCreateRetrieveAPIView):
    """
    Combined view for broadcasts that handles:
    - GET /broadcasts/ : List all broadcasts (with pagination)
    - GET /broadcasts/{id}/ : Get specific broadcast details
    - POST /broadcasts/ : Create and send a new broadcast

    Permissions:
        - Only accessible to active staff with manager+ permissions
    """

    permission_classes = ActiveManagerPermissions
    pagination_class = api_settings.DEFAULT_PAGINATION_CLASS
    lookup_url_kwarg = "broadcast_id"

    def get_serializer_class(self):
        """
        Choose the appropriate serializer based on the action.
        """
        if self.request.method == "POST":
            return BroadcastDetailSerializer
        elif hasattr(self, "kwargs") and self.lookup_url_kwarg in self.kwargs:
            return BroadcastDetailSerializer
        else:
            return BroadcastListSerializer

    def get_queryset(self):
        """
        Get the base queryset with appropriate optimizations.
        """
        queryset = Broadcast.objects.select_related("created_by__user")
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field

        if hasattr(self, "kwargs") and lookup_url_kwarg in self.kwargs:
            queryset = queryset.prefetch_related(
                models.Prefetch(
                    "logs", queryset=BroadcastLog.objects.order_by("-attempted_at")
                )
            ).order_by("-created_at")
        else:
            queryset = filter_broadcasts(queryset, self.request.query_params)
            queryset = queryset.order_by("-created_at")

        return queryset

    def list(self, request, *args, **kwargs):
        """
        List all broadcasts with summary data.
        """
        queryset = self.filter_queryset(self.get_queryset())

        # --- Caching for broadcast summary data ---
        cache_key = CacheKeys.BROADCAST_SUMMARY
        broadcast_summary_data = cache.get(cache_key)
        if not broadcast_summary_data:
            logger.info("Broadcast summary data not in cache. Calculating and caching.")
            broadcast_summary_data = Broadcast.objects.aggregate(
                total_broadcasts=Count("id"),
                sent_count=Count("id", filter=Q(status=Broadcast.Status.SENT)),
                pending_count=Count("id", filter=Q(status=Broadcast.Status.PENDING)),
                failed_count=Count("id", filter=Q(status=Broadcast.Status.FAILED)),
                partial_count=Count("id", filter=Q(status=Broadcast.Status.PARTIAL)),
                email_count=Count(
                    "id", filter=Q(mediums__contains=[Broadcast.Mediums.EMAIL])
                ),
                sms_count=Count(
                    "id", filter=Q(mediums__contains=[Broadcast.Mediums.SMS])
                ),
                whatsapp_count=Count(
                    "id", filter=Q(mediums__contains=[Broadcast.Mediums.WHATSAPP])
                ),
                platform_count=Count(
                    "id", filter=Q(mediums__contains=[Broadcast.Mediums.PLATFORM])
                ),
            )
            cache.set(
                cache_key, broadcast_summary_data, timeout=3600
            )  # Cache for 1 hour

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data["broadcast_summary_data"] = broadcast_summary_data
            response.data["results"] = response.data.pop("results")
            return response

        serializer = self.get_serializer(queryset, many=True)
        return Response(
            {
                "broadcast_summary_data": broadcast_summary_data,
                "results": serializer.data,
            }
        )

    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve a broadcast instance, using caching for performance.
        The cache is invalidated when the broadcast task completes.
        """
        broadcast_id = self.kwargs.get(self.lookup_url_kwarg)
        cache_key = CacheKeys.BROADCAST_DETAIL.format(broadcast_id=broadcast_id)

        # Try to fetch from cache first
        cached_data = cache.get(cache_key)
        if cached_data:
            logger.info(f"Returning cached data for broadcast {broadcast_id}")
            return Response(cached_data)

        # If not in cache, proceed with the standard retrieve logic
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        data = serializer.data

        # Cache the result for future requests
        cache.set(cache_key, data, timeout=3600)  # Cache for 1 hour
        return Response(data)

    def perform_create(self, serializer):
        """
        Handle the creation of a new broadcast.
        """
        broadcast = serializer.save(created_by=self.request.user.staff_profile)
        cache.delete(CacheKeys.BROADCAST_SUMMARY)

        logger.info(
            "Broadcast %s created by user %s. Scheduled: %s",
            broadcast.pk,
            self.request.user.pk,
            broadcast.scheduled_at,
        )

        def on_commit_hook():
            try:
                eta = None
                if broadcast.scheduled_at and broadcast.scheduled_at > timezone.now():
                    eta = broadcast.scheduled_at

                task_result = send_broadcast_task.apply_async(
                    args=[broadcast.pk],
                    eta=eta
                )

                Broadcast.objects.filter(pk=broadcast.pk).update(task_id=task_result.id)
                logger.info(
                    "Broadcast task queued for broadcast %s with task ID %s (ETA: %s)",
                    broadcast.pk,
                    task_result.id,
                    eta
                )
            except Exception as e:
                logger.error(
                    "Failed to queue broadcast task for broadcast %s: %s",
                    broadcast.pk,
                    str(e),
                )
                Broadcast.objects.filter(pk=broadcast.pk).update(
                    status=Broadcast.Status.FAILED_TO_QUEUE
                )

        transaction.on_commit(on_commit_hook)


class DatabaseBackupWebhookView(APIView):
    permission_classes = [HasXAPIKey]

    def post(self, request, *args, **kwargs):
        data = request.data
        from comms.services.slack import SlackService

        try:
            backup_log = BackupLog.objects.create(
                status=data.get("status"),
                environment=data.get("environment"),
                timestamp=datetime.fromisoformat(data.get("timestamp")),
                backup_filename=data.get("backup_filename"),
                error_message=data.get("error_message"),
            )
            logger.info(f"DB backup log created: {backup_log.id}")
            slack_service = SlackService()

            slack_service.send_backup_status(backup_log)

        except Exception as e:
            logger.error(f"Error processing DB backup webhook: {e}")
            return Response({"status": "error", "message": str(e)}, status=400)

        return Response({"status": "received"}, status=200)


class NotificationHistory(ListAPIView):
    """
    List all notifications for authenticated user and optional filtering.
    Can be filtered by 'status' query parameter to 'read' or 'unread'
    """

    permission_classes = AuthenticatedUser
    serializer_class = NotificationSerializer
    pagination_class = api_settings.DEFAULT_PAGINATION_CLASS

    def list(self, request, *args, **kwargs):
        user = request.user
        # Get current version (defaults to 0 if not set)
        version_key = CacheKeys.NOTIFICATIONS_VERSION.format(user_id=user.id)
        version = cache.get(version_key, 0)
        query_hash = hash(frozenset(request.query_params.items()))
        cache_key = CacheKeys.NOTIFICATIONS_LIST.format(
            user_id=user.id, version=version, query_hash=query_hash
        )

        cached_data = cache.get(cache_key)
        if cached_data:
            logger.info(f"Returning cached notifications for user {user.id}")
            return Response(cached_data)

        queryset = self.filter_queryset(self.get_queryset())

        # Stats cache also includes version
        stats_cache_key = CacheKeys.NOTIFICATION_STATS.format(user_id=user.id, version=version)
        stats = cache.get(stats_cache_key)
        if not stats:
            logger.info(
                f"Notification stats for user {user.id} not in cache. Aggregating and caching."
            )
            stats = Notification.objects.filter(recipient=user).aggregate(
                total_count=Count("id"),
                unread_count=Count("id", filter=Q(is_read=False)),
                read_count=Count("id", filter=Q(is_read=True)),
            )
            cache.set(stats_cache_key, stats, timeout=3600)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data["stats"] = stats
            cache.set(cache_key, response.data, 3600)
            return response

        serializer = self.get_serializer(queryset, many=True)
        response_data = {"stats": stats, "results": serializer.data}
        cache.set(cache_key, response_data, timeout=3600)
        return Response(response_data)

    def get_queryset(self):
        user = self.request.user
        queryset = Notification.objects.filter(recipient=user)

        status = self.request.query_params.get("status")
        if status == "read":
            queryset = queryset.filter(is_read=True)
        elif status == "unread":
            queryset = queryset.filter(is_read=False)

        return queryset


class MarkNotificationAsReadView(APIView):
    """
    Mark a specific notification as read for the authenticated user.
    """

    permission_classes = AuthenticatedUser

    def patch(self, request, notification_id):
        user = request.user
        try:
            notification = Notification.objects.get(id=notification_id, recipient=user)
            if not notification.is_read:
                notification.is_read = True
                notification.save()

                logger.info(
                    f"Notification {notification_id} marked as read for user {user.id}"
                )
            return Response({"status": "success"}, status=200)
        except Notification.DoesNotExist:
            return Response(
                {"status": "error", "message": "Notification not found"}, status=404
            )


class MarkAllNotificationsAsReadView(APIView):
    """
    Mark all notifications as read for the authenticated user.
    """

    permission_classes = AuthenticatedUser

    def patch(self, request):
        user = request.user
        updated_count = Notification.objects.filter(
            recipient=user, is_read=False
        ).update(is_read=True)

        if updated_count > 0:
            # Invalidate all notification caches by incrementing version
            version_key = CacheKeys.NOTIFICATIONS_VERSION.format(user_id=user.id)
            try:
                cache.incr(version_key)
            except ValueError:
                cache.set(version_key, 1, timeout=86400)

            logger.info(
                f"All notifications ({updated_count}) marked as read for user {user.id}"
            )

        return Response(
            {"status": "success", "updated_count": updated_count}, status=200
        )


class PublicSupportRequestView(CreateAPIView):
    """
    Public website support form (anonymous).
    Creates a PublicSupportRequest.
    """

    permission_classes = [AllowAny]
    serializer_class = PublicSupportRequestSerializer

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        from comms.tasks import send_system_email_task

        safe_data = sanitize_data(request.data)
        logger.info(f"Public support submission attempt: {safe_data}")

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        support_request = serializer.save()

        # Send confirmation email to the user
        send_system_email_task.delay(obj_id=support_request.id, is_public_support=True)

        # Send notification email to the support desk
        send_system_email_task.delay(
            obj_id=support_request.id, is_support_notification=True
        )

        logger.info(f"Public support request created: {support_request.id}")

        return Response(
            {"status": "success", "message": "Support request submitted successfully."},
            status=status.HTTP_201_CREATED,
        )


class SupportThreadView(APIView):
    """
    Get or create a support thread for the authenticated candidate.
    GET /support/thread/
    """
    permission_classes = AuthenticatedUser

    def get(self, request):
        user = request.user
        if not hasattr(user, "candidate_profile"):
            return Response({"error": "Only candidates can create support threads."}, status=status.HTTP_403_FORBIDDEN)

        thread, created = SupportChatThread.objects.get_or_create(candidate=user.candidate_profile)
        cache_key = CacheKeys.SUPPORT_THREAD_DETAIL.format(thread_id=thread.id)

        if created:
            # Insert system message on creation
            ThreadMessage.objects.create(
                thread=thread,
                sender=None,
                sender_type=ThreadMessage.SenderType.SYSTEM,
                text=f"Hello, {user.get_full_name()}. How can we help you today?"
            )
            # No need to check cache on creation
        else:
            # Check for unread messages first
            unread_messages = thread.messages.exclude(reads__user=user)
            if not unread_messages.exists():
                cached_data = cache.get(cache_key)
                if cached_data:
                    logger.info(f"Returning cached support thread detail for thread {thread.id}")
                    return Response(cached_data)

            # Mark unread messages as read (if any)
            if unread_messages.exists():
                MessageRead.objects.bulk_create(
                    [MessageRead(message=msg, user=user) for msg in unread_messages],
                    ignore_conflicts=True,
                )

        serializer = SupportChatThreadDetailSerializer(thread, context={"request": request})
        cache.set(cache_key, serializer.data, timeout=3600)
        return Response(serializer.data)


class StaffSupportThreadDetailView(RetrieveAPIView):
    """
    Retrieve full support thread and mark messages as read for staff.
    GET /staff/support/threads/{id}/
    """
    permission_classes = ActiveModeratorPermissions
    serializer_class = SupportChatThreadDetailSerializer
    queryset = SupportChatThread.objects.select_related("candidate", "assigned_staff__user").prefetch_related("messages__reads")
    lookup_field = "id"

    def get(self, request, *args, **kwargs):
        instance = self.get_object()
        cache_key = CacheKeys.SUPPORT_THREAD_DETAIL.format(thread_id=instance.id)

        # Check for unread messages first
        unread_messages = instance.messages.exclude(reads__user=request.user)

        # Only use cache if there are no unread messages
        if not unread_messages.exists():
            cached_data = cache.get(cache_key)
            if cached_data:
                logger.info(f"Returning cached support thread detail for thread {instance.id}")
                return Response(cached_data)

        # Mark unread messages as read (if any)
        if unread_messages.exists():
            MessageRead.objects.bulk_create(
                [MessageRead(message=msg, user=request.user) for msg in unread_messages],
                ignore_conflicts=True,
            )
            # Invalidate staff list cache since unread count will change
            try:
                cache.incr(CacheKeys.SUPPORT_THREADS_VERSION_STAFF)
            except ValueError:
                cache.set(CacheKeys.SUPPORT_THREADS_VERSION_STAFF, 1, timeout=86400)


        response = super().get(request, *args, **kwargs)
        cache.set(cache_key, response.data, timeout=3600)
        return response


class StaffSupportThreadListView(ListAPIView):
    """
    List all support threads for staff, ordered by unread count, online status, and last message.
    GET /staff/support/threads/
    """
    permission_classes = ActiveModeratorPermissions
    serializer_class = SupportChatThreadListSerializer

    def list(self, request, *args, **kwargs):
        user = request.user
        # Versioning for staff list
        version = cache.get(CacheKeys.SUPPORT_THREADS_VERSION_STAFF, 0)
        query_hash = hash(frozenset(request.query_params.items()))
        cache_key = CacheKeys.SUPPORT_THREAD_LIST_STAFF.format(
            user_id=user.id, version=version, query_hash=query_hash
        )

        cached_data = cache.get(cache_key)
        if cached_data:
            logger.info(f"Returning cached support threads for staff {user.id}")
            return Response(cached_data)

        response = super().list(request, *args, **kwargs)
        cache.set(cache_key, response.data, timeout=3600)
        return response

    def get_queryset(self):
        # Unread count annotation
        user = self.request.user
        queryset = SupportChatThread.objects.select_related("candidate", "assigned_staff__user") \
            .prefetch_related("messages__reads") \
            .annotate(
                unread_cnt=Count(
                    "messages",
                    filter=~Q(messages__reads__user=user),
                    distinct=True
                )
            )

        # Ordering:
        # 1. Unread count (desc)
        # 2. Candidate online status (online first) - Hard to do in DB since it's in Redis
        # 3. last_message_at (desc)
        # We'll order by unread_cnt and last_message_at in DB,
        # then sort by online status if necessary or just leave it for now.
        return queryset.order_by("-unread_cnt", "-last_message_at")


class SupportThreadMessageView(CreateAPIView):
    """
    Post a message to a support thread.
    POST /support/thread/{thread_id}/message/
    """
    permission_classes = AuthenticatedUser
    serializer_class = ThreadMessageSerializer

    @transaction.atomic
    def post(self, request, thread_id):
        try:
            thread = SupportChatThread.objects.get(id=thread_id)
        except SupportChatThread.DoesNotExist:
            return Response({"error": "Thread not found"}, status=status.HTTP_404_NOT_FOUND)

        # Validate user is either: Thread owner or Staff (Moderator+)
        is_staff = False
        if hasattr(request.user, "staff_profile"):
            from identity.permissions import StaffRoleHierarchy
            from identity.models import Staff
            is_staff = StaffRoleHierarchy.has_minimum_role(request.user.staff_profile.role, Staff.Roles.MODERATOR)

        is_owner = hasattr(request.user, "candidate_profile") and thread.candidate_id == request.user.candidate_profile.pk

        if not is_staff and not is_owner:
            return Response({"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        sender_type = ThreadMessage.SenderType.STAFF if is_staff else ThreadMessage.SenderType.CANDIDATE
        message = serializer.save(
            thread=thread,
            sender=request.user,
            sender_type=sender_type
        )

        # Broadcast via WebSocket group
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
        from comms.serializers import WebSocketThreadMessageSerializer
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"support_thread_{thread.id}",
            {
                "type": "chat.message",
                "message": WebSocketThreadMessageSerializer(message).data
            }
        )

        # Trigger staff load balancing if first staff reply
        if is_staff and thread.assigned_staff is None:
            self.assign_staff_automatically(thread, request.user.staff_profile)

        # Trigger escalation check if candidate sent message
        if sender_type == ThreadMessage.SenderType.CANDIDATE:
            from comms.tasks import support_escalation_task
            support_escalation_task.apply_async(
                args=[message.id],
                eta=message.created_at + timezone.timedelta(minutes=2)
            )

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def assign_staff_automatically(self, thread, current_staff):
        """
        Assign thread automatically to the staff with the lowest load.
        """
        from identity.models import Staff

        # Define active staff roles allowed to handle support
        support_roles = [Staff.Roles.SUPERADMIN, Staff.Roles.MANAGER, Staff.Roles.ADMIN, Staff.Roles.MODERATOR]

        # Find staff with lowest load (active threads they are assigned to)
        best_staff = Staff.objects.filter(
            user__is_active=True,
            role__in=support_roles
        ).annotate(
            load=Count(
                "assigned_chat_threads",
                filter=Q(assigned_chat_threads__status=SupportChatThread.Status.IN_PROGRESS)
            )
        ).order_by("load").first()

        if best_staff:
            thread.assigned_staff = best_staff
            thread.status = SupportChatThread.Status.IN_PROGRESS
            thread.save(update_fields=["assigned_staff", "status"])
