import logging
from datetime import datetime

from django.core.cache import cache
from django.db import models, transaction
from django.db.models import Count, Q
from django.utils.decorators import method_decorator
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import mixins
from rest_framework.generics import GenericAPIView, ListAPIView
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.views import APIView

from comms.models import BackupLog, Broadcast, BroadcastLog, Notification
from comms.serializers import (
    BroadcastDetailSerializer,
    BroadcastListSerializer,
    NotificationSerializer,
)
from comms.tasks import send_broadcast_task
from comms.utils import send_backup_status_to_slack
from identity.permissions import AuthenticatedUser, HasXAPIKey, ActiveManagerPermissions
from vmlc.utils.helpers import sanitize_data
from vmlc.utils.swagger_schemas import (
    api_key,
    bearer_auth,
    broadcast_detail_request_body,
    broadcast_detail_response_schema,
    broadcast_list_response_schema,
    error_response_400,
    error_response_401,
    error_response_403,
)


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


@method_decorator(
    name="get",
    decorator=swagger_auto_schema(
        operation_summary="List/retrieve Broadcast(s)",
        operation_description="List all broadcasts or retrieve a specific one.",
        responses={
            200: broadcast_list_response_schema,
            401: error_response_401,
            403: error_response_403,
        },
        tags=["Broadcast"],
        manual_parameters=[api_key, bearer_auth],
    ),
)
@method_decorator(
    name="post",
    decorator=swagger_auto_schema(
        operation_summary="Create Broadcast",
        operation_description="Create a new broadcast.",
        request_body=broadcast_detail_request_body,
        responses={
            201: broadcast_detail_response_schema,
            400: error_response_400,
            401: error_response_401,
            403: error_response_403,
        },
        tags=["Broadcast"],
        manual_parameters=[api_key, bearer_auth],
    ),
)
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
            queryset = queryset.order_by("-created_at")
            safe_params = sanitize_data(self.request.query_params)
            logger.info(
                f"BroadcastView (list): request from user {self.request.user.pk} "
                f"with query params: {safe_params}"
            )

        return queryset

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


@method_decorator(
    name="post",
    decorator=swagger_auto_schema(
        operation_summary="Webhook for Database Backups",
        operation_description="Receives status updates from the database backup script. This endpoint is protected by an API Key.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "status": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Backup status (e.g., 'success', 'first_failure', 'final_failure')",
                ),
                "environment": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Environment (e.g., 'prod', 'staging')",
                ),
                "timestamp": openapi.Schema(
                    type=openapi.TYPE_STRING, format=openapi.FORMAT_DATETIME
                ),
                "backup_filename": openapi.Schema(type=openapi.TYPE_STRING),
                "error_message": openapi.Schema(
                    type=openapi.TYPE_STRING, nullable=True
                ),
            },
            required=["status", "environment", "timestamp", "backup_filename"],
        ),
        responses={
            200: openapi.Response("Webhook received successfully."),
            400: error_response_400,
            403: error_response_403,
        },
        tags=["Webhooks"],
        manual_parameters=[api_key],
    ),
)
class DatabaseBackupWebhookView(APIView):
    permission_classes = [HasXAPIKey]

    def post(self, request, *args, **kwargs):
        data = request.data

        try:
            backup_log = BackupLog.objects.create(
                status=data.get("status"),
                environment=data.get("environment"),
                timestamp=datetime.fromisoformat(data.get("timestamp")),
                backup_filename=data.get("backup_filename"),
                error_message=data.get("error_message"),
            )
            logger.info(f"DB backup log created: {backup_log.id}")

            send_backup_status_to_slack(backup_log)

        except Exception as e:
            logger.error(f"Error processing DB backup webhook: {e}")
            return Response({"status": "error", "message": str(e)}, status=400)

        return Response({"status": "received"}, status=200)

@method_decorator(
    name="get",
    decorator=swagger_auto_schema(
        operation_summary="List notifications",
        operation_description="List all notifications for the authenticated user. Can be filtered by 'status' (read/unread).",
        manual_parameters=[
            api_key,
            bearer_auth,
            openapi.Parameter(
                "status",
                openapi.IN_QUERY,
                description="Filter by status: 'read' or 'unread'",
                type=openapi.TYPE_STRING,
            ),
        ],
        responses={
            200: NotificationSerializer(many=True),
            401: error_response_401,
        },
        tags=["Notifications"],
    ),
)
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
                unread_count=Count("id", filter=Q(is_read_by_recipient=False)),
                read_count=Count("id", filter=Q(is_read_by_recipient=True)),
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
            queryset = queryset.filter(is_read_by_recipient=True)
        elif status == "unread":
            queryset = queryset.filter(is_read_by_recipient=False)

        return queryset


class MarkNotificationAsReadView(APIView):
    """
    Mark a specific notification as read for the authenticated user.
    """

    permission_classes = AuthenticatedUser

    @swagger_auto_schema(
        operation_summary="Mark notification as read",
        operation_description="Mark a single notification as read by its ID.",
        manual_parameters=[api_key, bearer_auth],
        responses={
            200: openapi.Response("Notification marked as read."),
            404: error_response_400,
            401: error_response_401,
        },
        tags=["Notifications"],
    )
    def patch(self, request, notification_id):
        user = request.user
        try:
            notification = Notification.objects.get(id=notification_id, recipient=user)
            if not notification.is_read_by_recipient:
                notification.is_read_by_recipient = True
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

    @swagger_auto_schema(
        operation_summary="Mark all notifications as read",
        operation_description="Mark all unread notifications for the authenticated user as read.",
        manual_parameters=[api_key, bearer_auth],
        responses={
            200: openapi.Response("All notifications marked as read."),
            401: error_response_401,
        },
        tags=["Notifications"],
    )
    def patch(self, request):
        user = request.user
        updated_count = Notification.objects.filter(recipient=user, is_read_by_recipient=False).update(
            is_read_by_recipient=True
        )

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