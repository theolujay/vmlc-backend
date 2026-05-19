import logging

from rest_framework import status, parsers
from rest_framework.generics import CreateAPIView
from rest_framework.response import Response
from rest_framework.serializers import ValidationError
from rest_framework.permissions import AllowAny

from comms.tasks import send_welcome_mail_task
from identity.models import Candidate, Staff
from vmlc.models import FeatureFlag
from identity.serializers.registration import (
    PreRegUserSerializer,
    RegistrationV2Serializer,
)
from core.utils.exceptions import PermissionDenied
from core.utils.helpers import sanitize_data, invalidate_all_staff_dashboards

logger = logging.getLogger(__name__)


class RegistrationV2View(CreateAPIView):
    """
    V2 Registration endpoint for both Candidate and Volunteer.
    """

    permission_classes = [AllowAny]
    serializer_class = RegistrationV2Serializer
    parser_classes = (parsers.MultiPartParser, parsers.FormParser)

    def post(self, request, *args, **kwargs):
        safe_data = sanitize_data(request.data)
        logger.info(f"V2 Registration attempt with data: {safe_data}")

        if request.user.is_authenticated:
            logger.warning(
                f"Authenticated user {request.user.id} attempted to register."
            )
            raise PermissionDenied(
                "Already authenticated. Please log out to register a new account."
            )

        user_type = request.data.get("user_type")
        feature_flag_key = None

        from identity.tasks import clear_pre_reg_user

        if user_type == "candidate":
            feature_flag_key = "candidate_registration"
        elif user_type == "volunteer":
            feature_flag_key = "staff_registration"

        if feature_flag_key and not FeatureFlag.get_bool(
            feature_flag_key, default=False
        ):
            logger.warning(
                f"Registration attempt for {feature_flag_key} which is currently closed."
            )
            raise PermissionDenied(
                f"{feature_flag_key.replace('_', ' ').title()} is currently closed."
            )

        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            instance = serializer.save()
            clear_pre_reg_user.delay(
                user_email=instance.user.email, user_type=user_type
            )
        except ValidationError as e:
            logger.warning(f"Registration validation failed: {e.detail}")
            return Response(
                {
                    "status": "error",
                    "message": "Validation failed.",
                    "errors": e.detail,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        generated_password = getattr(instance, "_generated_password", None)
        if generated_password:
            send_welcome_mail_task.delay(
                user_id=instance.user.pk, generated_password=generated_password
            )

        if isinstance(instance, Candidate):
            from vmlc.utils.cache import (
                invalidate_candidate_cache,
                invalidate_staff_dashboard,
            )

            invalidate_candidate_cache(instance.pk, user_id=instance.user_id)
            invalidate_all_staff_dashboards()
            invalidate_staff_dashboard()
        elif isinstance(instance, Staff):
            from vmlc.utils.cache import invalidate_staff_dashboard

            invalidate_all_staff_dashboards()
            invalidate_staff_dashboard()

        logger.info(
            f"Successfully registered new user (v2) with email: {instance.user.email}"
        )

        return Response(
            {"status": "success", "message": "Action completed successfully."},
            status=status.HTTP_201_CREATED,
        )


class PreRegistrationView(CreateAPIView):
    """
    Pre-Registration endpoint for both Candidate and Volunteer.
    """

    permission_classes = [AllowAny]
    serializer_class = PreRegUserSerializer

    def post(self, request, *args, **kwargs):
        safe_data = sanitize_data(request.data)
        logger.info(f"Pre-Registration attempt with data: {safe_data}")

        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            pre_reg_user = serializer.save()

            from core.utils.events import log_event

            log_event(
                event_name="PRE_REGISTRATION",
                metadata={
                    "email": pre_reg_user.email,
                    "interest_type": pre_reg_user.interest_type,
                },
            )

            send_welcome_mail_task.delay(user_id=pre_reg_user.id, is_pre_reg=True)

            logger.info(
                f"Successfully pre-registered new user with email: {pre_reg_user.email}"
            )

            return Response(
                {"status": "success", "message": "Action completed successfully."},
                status=status.HTTP_201_CREATED,
            )
        except ValidationError as e:
            logger.warning(f"Pre-registration validation failed: {e.detail}")
            return Response(
                {
                    "status": "error",
                    "message": "Validation failed.",
                    "errors": e.detail,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
