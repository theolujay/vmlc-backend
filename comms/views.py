import logging
from datetime import datetime

from django.core.cache import cache
from django.db import models, transaction
from django.db.models import Count, Q
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
    SupportTicket,
    MessageRead,
)
from comms.serializers import (
    BroadcastDetailSerializer,
    BroadcastListSerializer,
    NotificationSerializer,
    PublicSupportRequestSerializer,
    SupportTicketDetailSerializer,
    SupportTicketListSerializer,
    TicketMessageSerializer,
)
from comms.tasks import send_broadcast_task
from identity.permissions import (
    HasXAPIKey,
    AuthenticatedUser,
    ActiveManagerPermissions,
    ActiveModeratorPermissions,
)
from vmlc.utils.helpers import sanitize_data
from vmlc.utils.query_filters import filter_broadcasts

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

        - For POST (create): Use detailed serializer for more fields
        - For GET with ID (retrieve): Use detailed serializer for full info
        - For GET without ID (list): Use list serializer for performance
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

        Different operations need different query optimizations:
        - List: Basic select_related for created_by__user (for MinimalStaffSerializer)
        - Retrieve: Additional prefetch_related for logs (for BroadcastDetailSerializer)
        """
        queryset = Broadcast.objects.select_related("created_by__user")
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field

        if hasattr(self, "kwargs") and lookup_url_kwarg in self.kwargs:
            queryset = queryset.prefetch_related(
                models.Prefetch(
                    "logs", queryset=BroadcastLog.objects.order_by("-attempted_at")
                )
            ).order_by("-created_at")
            logger.info(
                f"BroadcastView (retrieve): request from user {self.request.user.pk} "
                f"for broadcast {self.kwargs.get(lookup_url_kwarg)}"
            )
        else:
            queryset = filter_broadcasts(queryset, self.request.query_params)
            queryset = queryset.order_by("-created_at")
            safe_params = sanitize_data(self.request.query_params)
            logger.info(
                f"BroadcastView (list): request from user {self.request.user.pk} "
                f"with query params: {safe_params}"
            )

        return queryset

    def list(self, request, *args, **kwargs):
        """
        List all broadcasts with summary data.
        """
        queryset = self.filter_queryset(self.get_queryset())

        # --- Caching for broadcast summary data ---
        cache_key = "broadcast_summary_data"
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
        cache_key = f"broadcast_detail_{broadcast_id}"

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

        This method:
        1. Saves the broadcast with the current user as creator
        2. Triggers the async task to send the broadcast (after commit)
        3. Logs the action for auditing
        """
        broadcast = serializer.save(created_by=self.request.user.staff_profile)
        cache.delete("broadcast_summary_data")
        logger.info(
            "Broadcast %s created by user %s. Subject: '%s'",
            broadcast.pk,
            self.request.user.pk,
            broadcast.subject,
        )

        def on_commit_hook():
            try:
                task_result = send_broadcast_task.delay(broadcast.pk)
                Broadcast.objects.filter(pk=broadcast.pk).update(task_id=task_result.id)
                logger.info(
                    "Broadcast task queued for broadcast %s with task ID %s",
                    broadcast.pk,
                    task_result.id,
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
        version = cache.get(f"notifications_version_{user.id}", 0)
        query_hash = hash(frozenset(request.query_params.items()))
        cache_key = f"notifications_{user.id}_{version}_{query_hash}"

        cached_data = cache.get(cache_key)
        if cached_data:
            logger.info(f"Returning cached notifications for user {user.id}")
            return Response(cached_data)

        queryset = self.filter_queryset(self.get_queryset())

        # Stats cache also includes version
        stats_cache_key = f"notification_stats_{user.id}_{version}"
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

                # Invalidate all notification caches by incrementing version
                version_key = f"notifications_version_{user.id}"
                current_version = cache.get(version_key, 0)
                cache.set(version_key, current_version + 1, timeout=86400)

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
            version_key = f"notifications_version_{user.id}"
            current_version = cache.get(version_key, 0)
            cache.set(version_key, current_version + 1, timeout=86400)

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

        send_system_email_task.delay(obj_id=support_request.id, is_public_support=True)

        logger.info(f"Public support request created: {support_request.id}")

        return Response(
            {"status": "success", "message": "Support request submitted successfully."},
            status=status.HTTP_201_CREATED,
        )


class SupportConversationListView(ListAPIView):
    """
    List all support tickets (portal side).
    """

    permission_classes = ActiveModeratorPermissions
    serializer_class = SupportTicketListSerializer

    def get_queryset(self):
        return (
            SupportTicket.objects.select_related("assigned_to")
            .prefetch_related("messages__reads")
            .order_by("-last_message_at")
        )


class SupportConversationDetailView(RetrieveAPIView):
    """
    Retrieve full support ticket and mark messages as read.
    """

    permission_classes = ActiveModeratorPermissions
    serializer_class = SupportTicketDetailSerializer
    queryset = SupportTicket.objects.prefetch_related("messages__reads")
    lookup_field = "id"

    def get(self, request, *args, **kwargs):
        instance = self.get_object()

        # Mark unread messages as read for this staff user
        unread_messages = instance.messages.exclude(reads__user=request.user)

        MessageRead.objects.bulk_create(
            [MessageRead(message=msg, user=request.user) for msg in unread_messages],
            ignore_conflicts=True,
        )

        return super().get(request, *args, **kwargs)


class SupportReplyView(CreateAPIView):
    """
    Staff reply to a support ticket.
    """

    permission_classes = ActiveModeratorPermissions
    serializer_class = TicketMessageSerializer

    @transaction.atomic
    def post(self, request, ticket_id, *args, **kwargs):
        try:
            ticket = SupportTicket.objects.get(id=ticket_id)
        except SupportTicket.DoesNotExist:
            return Response(
                {"error": "Ticket not found"}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        message = serializer.save(
            ticket=ticket,
            sender=request.user,
        )

        # Update last message timestamp
        ticket.last_message_at = message.created_at
        ticket.save(update_fields=["last_message_at"])

        return Response(serializer.data, status=status.HTTP_201_CREATED)
