import logging

from django.db import models, transaction
from django.core.cache import cache
from django.utils.decorators import method_decorator
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework import mixins
from rest_framework.settings import api_settings
from rest_framework.response import Response
from rest_framework.generics import GenericAPIView

from comms.models import Broadcast, BroadcastLog
from comms.serializers import (
    BroadcastListSerializer,
    BroadcastDetailSerializer,
)
from comms.tasks import send_broadcast_task
from vmlc.permissions import VerifiedManagerPermissions
from vmlc.utils.exceptions import NotFound
from vmlc.utils.helpers import sanitize_data
from vmlc.utils.swagger_schemas import (
    api_key,
    bearer_auth,
    broadcast_list_response_schema,
    broadcast_detail_request_body,
    broadcast_detail_response_schema,
    error_response_400,
    error_response_401,
    error_response_403,
    error_response_404,
)


logger = logging.getLogger(__name__)


class ListCreateRetrieveAPIView(mixins.ListModelMixin, mixins.CreateModelMixin, mixins.RetrieveModelMixin, GenericAPIView):
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
        tags=['Broadcast'],
        manual_parameters=[api_key, bearer_auth]
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
        tags=['Broadcast'],
        manual_parameters=[api_key, bearer_auth]
    ),
)
class BroadcastView(ListCreateRetrieveAPIView):
    """
    Combined view for broadcasts that handles:
    - GET /broadcasts/ : List all broadcasts (with pagination)
    - GET /broadcasts/{id}/ : Get specific broadcast details
    - POST /broadcasts/ : Create and send a new broadcast
    
    Permissions:
        - Only accessible to verified staff with manager+ permissions
    """
    permission_classes = VerifiedManagerPermissions
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
        elif hasattr(self, 'kwargs') and self.lookup_url_kwarg in self.kwargs:
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
        
        if hasattr(self, 'kwargs') and lookup_url_kwarg in self.kwargs:
            queryset = queryset.prefetch_related(
                models.Prefetch(
                    "logs",
                    queryset=BroadcastLog.objects.order_by("-attempted_at")
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
            broadcast.subject
        )

        def on_commit_hook():
            try:
                task_result = send_broadcast_task.delay(broadcast.pk)
                Broadcast.objects.filter(pk=broadcast.pk).update(task_id=task_result.id)
                logger.info(
                    "Broadcast task queued for broadcast %s with task ID %s",
                    broadcast.pk, task_result.id
                )
            except Exception as e:
                logger.error("Failed to queue broadcast task for broadcast %s: %s", broadcast.pk, str(e))
                Broadcast.objects.filter(pk=broadcast.pk).update(status=Broadcast.Status.FAILED_TO_QUEUE)

        transaction.on_commit(on_commit_hook)