import logging
from datetime import timedelta, datetime

from django.utils import timezone 
from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse
from django.conf import settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.generics import CreateAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from datetime import timedelta

from vmlc.permissions import VerifiedManagerPermissions
from vmlc.serializers import StaffInviteSerializer
from vmlc.tasks import send_mail_task, revoke_staff_invite_task
from vmlc.models import Staff
from vmlc.utils.swagger_schemas import (
    api_key,
    bearer_auth,
    error_response_400,
    error_response_401,
    error_response_403,
    staff_registration_request_body,
)

logger = logging.getLogger(__name__)


class StaffInviteView(CreateAPIView):
    """
    API view to create a new staff member.
    """
    permission_classes = VerifiedManagerPermissions
    serializer_class = StaffInviteSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user.staff_profile)

    @swagger_auto_schema(
        operation_summary="Create Staff Member",
        operation_description="Creates a new staff member with the provided details.",
        request_body=staff_registration_request_body,
        responses={
            201: openapi.Response("Staff member created successfully."),
            400: error_response_400,
            401: error_response_401,
            403: error_response_403,
        },
        tags=["Staff Management"],
        manual_parameters=[api_key, bearer_auth],
    )
    def post(self, request, *args, **kwargs):
        temp_password = request.data.get("password")
        login_url = f"{settings.FRONTEND_BASE_URL}/auth/login/" # TODO: make this dynamic rather than hard-coded
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        # Calculate the time delta based on environment
        revoke_delta = timedelta(days=7) if not settings.DEBUG else timedelta(minutes=5)
        time_to_revoke = timezone.now() + revoke_delta

        # Schedule the revocation task to run after 'time_to_revoke'
        revoke_staff_invite_task.apply_async(
            args=[serializer.instance.user.id],
            eta=time_to_revoke
        )

        staff_profile = serializer.instance
        user = staff_profile.user

        # Dynamically generate the human-readable time string
        if not settings.DEBUG:
            time_to_revoke_str = f"{revoke_delta.days} days"
        else:
            time_to_revoke_str = f"{revoke_delta.seconds // 60} minutes"
        send_mail_task.delay(
            subject="Staff Invite to Verboheit MLC",
            message = (
                f"Hello {user.get_full_name()},\n\n"
                f"You've been invited to join the Verboheit Mathematics League Competition "
                f"{timezone.now().year} as a staff member. To accept, log in using the link "
                f"below with this email and the temporary password provided. Remember to change"
                f"it after login. If you choose not to accept, simply ignore this message. "
                f"Note that the credentials will expire in {time_to_revoke_str} if you don't log in.\n\n"
                f"Password: {temp_password}\n"
                f"Login: {login_url}\n\n"
                f"Regards,\n"
                f"Verboheit MLC Management"
            ),
            recipient_list=[user.email],
        )
        headers = self.get_success_headers({})
        logger.info(
            f"Staff profile created successfully with email: {user.email} by {request.user.email}"
        )
        return Response(
            {"message": "Staff profile created, invite sent."},
            status=status.HTTP_201_CREATED,
            headers=headers,
        )
