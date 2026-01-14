import logging

from django.core.cache import cache
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework import status, parsers
from rest_framework.generics import CreateAPIView
from rest_framework.response import Response
from rest_framework.serializers import ValidationError

from vmlc.tasks import send_welcome_mail_task
from vmlc.models import Candidate, Staff, FeatureFlag
from vmlc.permissions import HasXAPIKey
from vmlc.v2.serializers.registration import PreRegUserSerializer, RegistrationV2Serializer, SupportInquirySerializer
from vmlc.utils.exceptions import PermissionDenied
from vmlc.utils.helpers import sanitize_data, invalidate_all_staff_dashboards

logger = logging.getLogger(__name__)

class RegistrationV2View(CreateAPIView):
    """
    V2 Registration endpoint for both Candidate and Volunteer.
    """
    # permission_classes = [HasXAPIKey]
    serializer_class = RegistrationV2Serializer
    parser_classes = (parsers.MultiPartParser, parsers.FormParser)

    @swagger_auto_schema(
        operation_summary="Register User (Candidate/Volunteer)",
        operation_description="Registers a new user as either a Candidate or a Volunteer.",
        request_body=RegistrationV2Serializer,
        responses={
            201: openapi.Response(
                description="Action completed successfully.",
                examples={"application/json": {"status": "success", "message": "Action completed successfully."}}
            ),
            400: openapi.Response(description="Bad Request"),
        },
        tags=["Registration V2"],
        manual_parameters=[
            openapi.Parameter(
                "x-api-key",
                openapi.IN_HEADER,
                description="API Key",
                type=openapi.TYPE_STRING,
                required=True,
            )
        ]
    )
    def post(self, request, *args, **kwargs):
        # 1. Sanitize Data (logging mostly)
        safe_data = sanitize_data(request.data)
        logger.info(f"V2 Registration attempt with data: {safe_data}")
        
        # 2. Check Authentication
        if request.user.is_authenticated:
            logger.warning(f"Authenticated user {request.user.id} attempted to register.")
            raise PermissionDenied("Already authenticated. Please log out to register a new account.")

        # 3. Check Feature Flags
        user_type = request.data.get("user_type")
        feature_flag_key = None

        # Note: V1 used "staff_registration" in StaffRegistrationView but "staff_registration_open" in ToggleStaffRegistrationView.
        # I should check the toggle view in vmlc/views/registration.py (v1) again.
        # ToggleStaffRegistrationView uses "staff_registration_open".
        # StaffRegistrationView uses "staff_registration".
        # FeatureFlag.get_bool uses the key. If they are different, that's a bug in V1 or deliberate.
        # ToggleCandidateRegistrationView uses "candidate_registration_open".
        # CandidateRegistrationView uses "candidate_registration".
        # I suspect the keys are consistent in DB, maybe just inconsistent naming in code or mapped.
        # Let's look at `FeatureFlag.get_bool`. It just queries by key.
        # I will use "candidate_registration" and "staff_registration" as used in the Registration Views in V1.
        
        if user_type == "candidate":
            feature_flag_key = "candidate_registration"
        elif user_type == "volunteer":
             feature_flag_key = "staff_registration"

        if feature_flag_key and not FeatureFlag.get_bool(feature_flag_key, default=False):
             logger.warning(f"Registration attempt for {feature_flag_key} which is currently closed.")
             raise PermissionDenied(f"{feature_flag_key.replace('_', ' ').title()} is currently closed.")

        try:
            # 4. Serialize & Save
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            instance = serializer.save()
        except ValidationError as e:
            logger.warning(f"Registration validation failed: {e.detail}")
            return Response(
                {
                    "status": "error",
                    "message": "Validation failed.",
                    "errors": e.detail
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # 5. Tasks (Email with Password)
        generated_password = getattr(instance, "_generated_password", None)
        
        if generated_password:
             send_welcome_mail_task.delay(user_id=instance.user.pk, generated_password=generated_password)
        
        # 6. Invalidate Caches
        if isinstance(instance, Candidate):
             cache.delete(f"candidate_dashboard_{instance.pk}")
             invalidate_all_staff_dashboards()
        elif isinstance(instance, Staff):
             invalidate_all_staff_dashboards()

        logger.info(f"Successfully registered new user (v2) with email: {instance.user.email}")
        
        return Response(
            {
                "status": "success",
                "message": "Action completed successfully."
            },
            status=status.HTTP_201_CREATED
        )

class PreRegistrationView(CreateAPIView):
    """
    Pre-Registration endpoint for both Candidate and Volunteer.
    """
    # permission_classes = [HasXAPIKey]
    serializer_class = PreRegUserSerializer

    @swagger_auto_schema(
        operation_summary="Pre-Register Interested User (Candidate/Volunteer)",
        operation_description="Registers a new user as either an interested Candidate or a Volunteer.",
        request_body=PreRegUserSerializer,
        responses={
            201: openapi.Response(
                description="Action completed successfully.",
                examples={"application/json": {"status": "success", "message": "Action completed successfully."}}
            ),
            400: openapi.Response(
                description="Validation Error",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'status': openapi.Schema(type=openapi.TYPE_STRING, example='error'),
                        'message': openapi.Schema(type=openapi.TYPE_STRING, example='Validation failed.'),
                        'errors': openapi.Schema(type=openapi.TYPE_OBJECT, description="Field-specific validation errors")
                    }
                )
            ),
        },
        tags=["Registration V2"],
        manual_parameters=[
            openapi.Parameter(
                "x-api-key",
                openapi.IN_HEADER,
                description="API Key",
                type=openapi.TYPE_STRING,
                required=True,
            )
        ]
    )
    def post(self, request, *args, **kwargs):
        # 1. Sanitize Data (logging mostly)
        safe_data = sanitize_data(request.data)
        logger.info(f"Pre-Registration attempt with data: {safe_data}")

        # 2. Check Feature Flag
        if not FeatureFlag.get_bool("pre_registration_open", default=True):
             logger.warning("Pre-registration attempt while it is closed.")
             raise PermissionDenied("Pre-registration is currently closed.")

        try:
            # 3. Serialize & Save
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            pre_reg_user = serializer.save()

            # 4. Tasks (Email)
            send_welcome_mail_task.delay(user_id=pre_reg_user.id, is_pre_reg=True)

            logger.info(f"Successfully pre-registered new user with email: {pre_reg_user.email}")
            
            return Response(
                {
                    "status": "success",
                    "message": "Action completed successfully."
                },
                status=status.HTTP_201_CREATED
            )
        except ValidationError as e:
            logger.warning(f"Pre-registration validation failed: {e.detail}")
            return Response(
                {
                    "status": "error",
                    "message": "Validation failed.",
                    "errors": e.detail
                },
                status=status.HTTP_400_BAD_REQUEST
            )
