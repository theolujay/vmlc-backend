import logging

from django.db import transaction
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.generics import CreateAPIView, ListAPIView, RetrieveAPIView
from rest_framework.response import Response
from rest_framework.serializers import ValidationError
from rest_framework.permissions import AllowAny

from vmlc.models import SupportInquiry, SupportMessage
from identity.permissions import ActiveModeratorPermissions
from vmlc.utils.helpers import sanitize_data
from vmlc.v2.serializers.support import (
    SupportInquirySerializer,
    SupportConversationSerializer,
    SupportConversationDetailSerializer,
    SupportMessageSerializer,
)

logger = logging.getLogger(__name__)


class SupportUsView(CreateAPIView):
    """
    API View to handle 'Support Us' inquiries.
    Authentication: x-api-key required.
    """

    permission_classes = [AllowAny]
    serializer_class = SupportInquirySerializer

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        from vmlc.tasks import send_system_email_task

        safe_data = sanitize_data(request.data)
        logger.info(f"Support inquiry submission attempt with data: {safe_data}")

        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            # Link to user if authenticated
            extra_data = {}
            if request.user.is_authenticated:
                extra_data["user"] = request.user

            support_inquiry = serializer.save(**extra_data)

            # Create initial message
            SupportMessage.objects.create(
                inquiry=support_inquiry,
                sender=request.user if request.user.is_authenticated else None,
                sender_profile=(
                    "candidate" if request.user.is_authenticated else "guest"
                ),
                text=support_inquiry.message,
                is_read_by_user=True,
                is_read_by_staff=False,
            )

            send_system_email_task.delay(
                obj_id=support_inquiry.id, is_support_inquiry=True
            )
            send_system_email_task.delay(
                obj_id=support_inquiry.id, is_support_notification=True
            )

            logger.info(
                f"Successfully registered support inquiry with email: {support_inquiry.email}"
            )

            return Response(
                {
                    "status": "success",
                    "message": "Support inquiry submitted successfully.",
                },
                status=status.HTTP_201_CREATED,
            )
        except ValidationError as e:
            logger.warning(f"Support inquiry validation failed: {e.detail}")
            return Response(
                {
                    "status": "error",
                    "message": "Support inquiry submission failed.",
                    "errors": e.detail,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )


class SupportConversationListView(ListAPIView):
    """
    List all support inquiries as conversations.
    Accessible by Moderators and higher.
    """

    permission_classes = ActiveModeratorPermissions
    serializer_class = SupportConversationSerializer
    queryset = SupportInquiry.objects.all().prefetch_related("messages")

    @swagger_auto_schema(
        operation_summary="List Support Conversations",
        operation_description="Retrieve a list of all support inquiries with last message previews and unread counts.",
        tags=["Support"],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class SupportConversationDetailView(RetrieveAPIView):
    """
    Retrieve full conversation history and manage read status.
    """

    permission_classes = ActiveModeratorPermissions
    serializer_class = SupportConversationDetailSerializer
    queryset = SupportInquiry.objects.all()
    lookup_field = "id"

    @swagger_auto_schema(
        operation_summary="Get Support Conversation Detail",
        operation_description="Retrieve full message history for a specific support inquiry.",
        tags=["Support"],
    )
    def get(self, request, *args, **kwargs):
        instance = self.get_object()
        # Mark all messages as read by staff when they open the conversation
        instance.messages.filter(is_read_by_staff=False).update(is_read_by_staff=True)
        return super().get(request, *args, **kwargs)


class SupportReplyView(CreateAPIView):
    """
    Staff reply to a support conversation.
    """

    permission_classes = ActiveModeratorPermissions
    serializer_class = SupportMessageSerializer

    @swagger_auto_schema(
        operation_summary="Reply to Support Conversation",
        operation_description="Send a message in a support conversation thread.",
        tags=["Support"],
    )
    @transaction.atomic
    def post(self, request, inquiry_id, *args, **kwargs):
        try:
            inquiry = SupportInquiry.objects.get(id=inquiry_id)
        except SupportInquiry.DoesNotExist:
            return Response(
                {"error": "Inquiry not found"}, status=status.HTTP_404_NOT_FOUND
            )

        staff_profile = getattr(request.user, "staff_profile", None)
        role = staff_profile.role if staff_profile else "staff"

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        serializer.save(
            inquiry=inquiry,
            sender=request.user,
            sender_profile=role,
            is_read_by_staff=True,  # Staff sent it
            is_read_by_user=False,
        )

        # Update inquiry status to in_progress if it was open
        if inquiry.status == SupportInquiry.Status.OPEN:
            inquiry.status = SupportInquiry.Status.IN_PROGRESS
            inquiry.save(update_fields=["status", "updated_at"])

        return Response(serializer.data, status=status.HTTP_201_CREATED)
