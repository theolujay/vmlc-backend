import logging

import boto3
from botocore.exceptions import ClientError
from django.core.cache import cache
from django.db import transaction
from django.http import HttpResponse
from django.utils.decorators import method_decorator

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.views import APIView

from vmlc.models import User, UserVerification
from vmlc.permissions import (
    AuthenticatedUser,
    IsObjectOwnerOrManagerRole,
    VerifiedManagerPermissions,
)
from vmlc.serializers import (
    UserVerificationActionSerializer,
    UserVerificationListSerializer,
    UserVerificationStatusSerializer,
    UserVerificationUploadSerializer,
)
from vmlc.tasks import send_mail_task, validate_user_verification_files_task
from vmlc.utils.exceptions import (
    APIException,
    NotFound,
    PermissionDenied,
    ValidationError,
)
from vmlc.utils.helpers import invalidate_all_staff_dashboards
from vmlc.utils.swagger_schemas import (
    api_key,
    bearer_auth,
    error_response_400,
    error_response_401,
    error_response_403,
    error_response_404,
    user_verification_action_request_body,
    user_verification_list_response_schema,
    user_verification_status_response_schema,
)

logger = logging.getLogger(__name__)


class UserVerificationStatusView(APIView):
    """
    Get the verification status of the authenticated user.
    """

    permission_classes = AuthenticatedUser

    @swagger_auto_schema(
        operation_summary="Get User Verification Status",
        operation_description="Get the verification status of a user.",
        responses={
            200: user_verification_status_response_schema,
            401: error_response_401,
            403: error_response_403,
            404: error_response_404,
        },
        tags=["User Verification"],
        manual_parameters=[api_key, bearer_auth],
    )
    def get(self, request, user_id=None):
        logger.info(
            f"UserVerificationStatusView: request from user {request.user.id} for user {user_id}"
        )
        # Determine target user
        if user_id is None:
            target_user = request.user
        else:
            try:
                target_user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                logger.error(f"User with id {user_id} not found.")
                raise NotFound("User not found.")
            if (
                request.user.id != target_user.id
                and not IsObjectOwnerOrManagerRole().has_object_permission(
                    self.request, self, target_user
                )
            ):
                logger.warning(
                    f"User {request.user.id} does not have permission to access user {user_id}'s verification status."
                )
                raise PermissionDenied(
                    "You don't have permission to access this user's verification status."
                )

        cache_key = f"user_verification_status_{target_user.id}"
        cached_data = cache.get(cache_key)
        if cached_data:
            return Response(cached_data)

        # Check email verification first
        if not target_user.is_email_verified:
            logger.warning(f"User {target_user.id} has not verified their email.")
            response_data = {
                "status": "email_not_verified",
                "detail": "Email not verified. Verify email for user verification.",
            }
            cache.set(cache_key, response_data, 86400)
            return Response(response_data, status=status.HTTP_200_OK)

        # Get or create verification record
        verification, _ = UserVerification.objects.get_or_create(user=target_user)

        # Determine status based on verification record
        if verification.is_approved:
            logger.info(f"User {target_user.id} is verified.")
            response_data = {"status": "verified", "detail": "User is verified."}
            cache.set(cache_key, response_data, 86400)
            return Response(response_data, status=status.HTTP_200_OK)

        if verification.is_pending:
            # Return detailed verification data for pending cases
            serializer = UserVerificationStatusSerializer(verification)
            logger.info(f"User {target_user.id} has a pending verification request.")
            response_data = {
                "status": "pending",
                "detail": "Verification request is pending review.",
                "verification_data": serializer.data,
            }
            cache.set(cache_key, response_data, 86400)
            return Response(response_data, status=status.HTTP_200_OK)

        if verification.is_rejected:
            logger.info(f"User {target_user.id} has a rejected verification request.")
            response_data = {
                "status": "rejected",
                "detail": "Verification request was rejected. You may resubmit with updated documents.",
            }
            cache.set(cache_key, response_data, 86400)
            return Response(response_data, status=status.HTTP_200_OK)

        # Not verified, not pending, not rejected = never submitted
        logger.info(f"User {target_user.id} has not submitted a verification request.")
        response_data = {
            "status": "not_submitted",
            "detail": "No verification request submitted.",
        }
        cache.set(cache_key, response_data, 86400)
        return Response(response_data, status=status.HTTP_200_OK)


@method_decorator(
    name="post",
    decorator=swagger_auto_schema(
        operation_summary="Upload Verification Documents",
        operation_description="Upload verification documents for the authenticated user.",
        manual_parameters=[
            openapi.Parameter(
                "face_id",
                openapi.IN_FORM,
                type=openapi.TYPE_FILE,
                description="Face ID",
                required=True,
            ),
            openapi.Parameter(
                "id_card",
                openapi.IN_FORM,
                type=openapi.TYPE_FILE,
                description="ID card",
                required=True,
            ),
            openapi.Parameter(
                "verification_document",
                openapi.IN_FORM,
                type=openapi.TYPE_FILE,
                description="Verification document",
                required=True,
            ),
            openapi.Parameter(
                "verification_document_type",
                openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                description="The type of the verification document provided (e.g., 'Birth Certificate', 'NIN').",
                required=False,
            ),
            api_key,
            bearer_auth,
        ],
        responses={
            202: openapi.Response(
                "Documents uploaded successfully. Validation is in progress."
            ),
            400: error_response_400,
            401: error_response_401,
            403: error_response_403,
        },
        tags=["User Verification"],
    ),
)
@method_decorator(
    name="patch",
    decorator=swagger_auto_schema(
        operation_summary="Update Verification Documents",
        operation_description="Update verification documents for the authenticated user.",
        manual_parameters=[
            openapi.Parameter(
                "face_id",
                openapi.IN_FORM,
                type=openapi.TYPE_FILE,
                description="Face ID",
            ),
            openapi.Parameter(
                "id_card",
                openapi.IN_FORM,
                type=openapi.TYPE_FILE,
                description="ID card",
            ),
            openapi.Parameter(
                "verification_document",
                openapi.IN_FORM,
                type=openapi.TYPE_FILE,
                description="Verification document",
            ),
            openapi.Parameter(
                "verification_document_type",
                openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                description="The type of the verification document provided.",
            ),
            api_key,
            bearer_auth,
        ],
        responses={
            202: openapi.Response(
                "Verification data updated successfully. Validation is in progress."
            ),
            400: error_response_400,
            401: error_response_401,
            403: error_response_403,
            404: error_response_404,
        },
        tags=["User Verification"],
    ),
)
class UserVerificationUploadView(APIView):
    """
    Upload verification documents for the authenticated user.
    """

    permission_classes = AuthenticatedUser
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        return self._upload_verification_documents(request)

    def patch(self, request):
        return self._update_verification_documents(request)

    def _upload_verification_documents(self, request):
        logger.info(f"UserVerificationUploadView: request from user {request.user.id}")
        verification, created = UserVerification.objects.get_or_create(
            user=request.user
        )
        if created:
            logger.info(
                "New user verification object created during upload - likely failed at email verification step prior."
            )

        # Check current status before processing
        if not verification.user.is_email_verified:
            logger.warning(f"User {request.user.id} has not verified their email.")
            raise PermissionDenied(
                "Email not verified. Please verify your email before uploading documents."
            )

        if verification.is_approved:
            logger.warning(f"User {request.user.id} is already verified.")
            raise ValidationError("This user is already verified.")

        if verification.is_pending:
            logger.warning(
                f"User {request.user.id} has a pending verification request."
            )
            raise ValidationError("User already has a verification request pending.")

        serializer = UserVerificationUploadSerializer(
            verification, data=request.data, partial=True
        )

        if serializer.is_valid():
            with transaction.atomic():
                # Set as pending and clear rejection status when submitting/resubmitting
                verification = serializer.save(is_pending=True, is_rejected=False)

            # Asynchronously validate the files
            validate_user_verification_files_task.delay(verification.id)

            # Send confirmation email
            user = request.user
            email_subject = "Your Verification Documents Have Been Received"
            email_message = (
                f"Dear {user.get_full_name()},\n\n"
                "This is to confirm that we have received your verification documents. "
                "Our team will review them shortly.\n\n"
                "You will receive another email once the review process is complete.\n\n"
                "Best Regards,\nManagement."
            )
            send_mail_task.delay(
                subject=email_subject,
                message=email_message,
                recipient_list=[user.email],
            )

            # Invalidate caches
            cache.delete(f"user_verification_status_{request.user.id}")
            cache.delete(f"account_management_{request.user.id}")
            cache.delete("stats_overview")
            if hasattr(request.user, "candidate_profile"):
                cache.delete(f"candidate_dashboard_{request.user.candidate_profile.pk}")

            logger.info(
                "Verification data submitted by user %s. Validation is pending.",
                request.user.id,
            )
            return Response(
                {
                    "detail": "Documents uploaded successfully. Validation is in progress.",
                    "verification_data": {
                        "status": "pending_validation",
                        "has_face_id": bool(verification.face_id),
                        "has_id_card": bool(verification.id_card),
                        "has_verification_document": bool(
                            verification.verification_document
                        ),
                    },
                },
                status=status.HTTP_202_ACCEPTED,
            )
        logger.warning(
            f"UserVerificationUploadView: validation failed: {serializer.errors}"
        )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def _update_verification_documents(self, request):
        """Update existing verification data (partial update)."""
        logger.info(
            f"UserVerificationUploadView (patch): request from user {request.user.id}"
        )
        try:
            verification = UserVerification.objects.get(user=request.user)
        except UserVerification.DoesNotExist:
            logger.error(f"No verification data found for user {request.user.id}")
            raise NotFound("No verification data found for this user.")

        if verification.is_approved:
            logger.warning(
                f"Cannot update verification data for already verified user {request.user.id}"
            )
            raise ValidationError(
                "Cannot update verification data for an already verified user."
            )

        serializer = UserVerificationUploadSerializer(
            verification, data=request.data, partial=True
        )

        if serializer.is_valid():
            with transaction.atomic():
                # Keep as pending or set to pending, clear rejection if updating
                verification = serializer.save(is_pending=True, is_rejected=False)

            # Asynchronously validate the files
            validate_user_verification_files_task.delay(verification.id)

            # Send confirmation email
            user = request.user
            email_subject = "Your Verification Documents Have Been Updated"
            email_message = (
                f"Dear {user.get_full_name()},\n\n"
                "This is to confirm that we have received your updated verification documents. "
                "Our team will review them shortly.\n\n"
                "You will receive another email once the review process is complete.\n\n"
                "Best Regards,\nManagement."
            )
            send_mail_task.delay(
                subject=email_subject,
                message=email_message,
                recipient_list=[user.email],
            )

            # Invalidate caches
            cache.delete(f"user_verification_status_{request.user.id}")
            if hasattr(request.user, "candidate_profile"):
                cache.delete(f"candidate_dashboard_{request.user.candidate_profile.pk}")

            logger.info(
                "Verification data updated by user %s. Validation is pending.",
                request.user.id,
            )

            return Response(
                {
                    "detail": "Verification data updated successfully. Validation is in progress.",
                    "verification_data": {
                        "status": "pending_validation",
                        "has_face_id": bool(verification.face_id),
                        "has_id_card": bool(verification.id_card),
                        "has_verification_document": bool(
                            verification.verification_document
                        ),
                    },
                },
                status=status.HTTP_202_ACCEPTED,
            )
        logger.warning(
            f"UserVerificationUploadView (patch): validation failed: {serializer.errors}"
        )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserVerificationDocumentView(APIView):
    """
    Access verification documents for authenticated user or any user (if superadmin).
    """

    permission_classes = AuthenticatedUser

    @swagger_auto_schema(
        operation_summary="Get Verification Document",
        operation_description="Access verification documents for a user.",
        responses={
            200: openapi.Response("File content"),
            401: error_response_401,
            403: error_response_403,
            404: error_response_404,
        },
        tags=["User Verification"],
        manual_parameters=[api_key, bearer_auth],
    )
    def get(self, request, file_type, user_id=None):
        file, storage_prefix, _ = self._get_verification_document(
            request, file_type, user_id
        )

        try:
            s3_client = boto3.client("s3")
            bucket_name = "vmlc-s3"
            object_key = f"{storage_prefix}/{file.name}"

            logger.info(f"Accessing S3: bucket='{bucket_name}', key='{object_key}'")

            # Get the object from S3
            s3_response = s3_client.get_object(Bucket=bucket_name, Key=object_key)

            # Get content type
            content_type = s3_response.get("ContentType", "application/octet-stream")

            # Stream the content
            file_content = s3_response["Body"].read()

            return HttpResponse(file_content, content_type=content_type)

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "NoSuchKey":
                logger.error(f"S3 object not found: {object_key}")
                raise NotFound(
                    f"The {file_type.replace('_', ' ')} file is no longer available."
                )
            if error_code == "AccessDenied":
                logger.error(f"S3 access denied: {object_key}")
                raise PermissionDenied("Access denied to file storage.")

            logger.error(f"S3 error ({error_code}): {e}")
            exc = APIException(
                "Could not retrieve file from storage.",
            )
            exc.status_code = status.HTTP_502_BAD_GATEWAY
            raise exc
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise APIException("Could not retrieve file from storage.")

    def _get_verification_document(self, request, file_type, user_id=None):
        logger.info(
            f"UserVerificationDocumentView: request from user {request.user.id} for file type {file_type} of user {user_id}"
        )
        # If no user_id provided, default to current user
        if user_id is None:
            target_user = request.user
            try:
                verification = UserVerification.objects.get(user=request.user)
            except UserVerification.DoesNotExist:
                logger.error(f"User verification not found for user {request.user.id}")
                raise NotFound("User verification not found.")
        else:
            # user_id provided - superadmin accessing another user's files
            try:
                target_user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                logger.error(f"User with id {user_id} not found.")
                raise NotFound("User not found.")

            # Check permissions: only the user themselves or superadmin can access
            if str(request.user.id) != str(
                user_id
            ) and not IsObjectOwnerOrManagerRole().has_object_permission(  # Convert both to string for comparison
                request, self, target_user
            ):
                logger.warning(
                    f"User {request.user.id} does not have permission to access user {user_id}'s documents."
                )
                raise PermissionDenied(
                    "You don't have permission to access this user's documents."
                )
            try:
                verification = UserVerification.objects.get(user=target_user)
            except UserVerification.DoesNotExist:
                logger.error(f"User verification not found for user {target_user.id}")
                raise NotFound("User verification not found.")

        if user_id and str(request.user.id) != str(user_id):
            logger.info(
                "Superadmin %s accessing %s for user %s",
                request.user.id,
                file_type,
                user_id,
            )

        # Get the file field and determine storage path
        if file_type == "id_card":
            file = verification.id_card
            storage_prefix = "media/private"  # PrivateMediaStorage
        elif file_type == "verification_document":
            file = verification.verification_document
            storage_prefix = "media/private"  # PrivateMediaStorage
        elif file_type == "face_id":
            file = verification.face_id
            storage_prefix = "media/public"  # PublicMediaStorage
        else:
            logger.error(f"Invalid file type: {file_type}")
            raise ValidationError("Invalid file type.")

        if not file or not file.name:
            logger.error(
                f"No {file_type.replace('_', ' ')} uploaded for user {target_user.id}"
            )
            raise NotFound(f"No {file_type.replace('_', ' ')} uploaded.")

        return file, storage_prefix, target_user


@method_decorator(
    name="get",
    decorator=swagger_auto_schema(
        operation_summary="List Verification Requests",
        operation_description="List all verification requests for manager review.",
        responses={
            200: user_verification_list_response_schema,
            401: error_response_401,
            403: error_response_403,
        },
        tags=["User Verification"],
        manual_parameters=[api_key, bearer_auth],
    ),
)
class UserVerificationListView(ListAPIView):
    """List all verification requests for superadmin review."""

    permission_classes = VerifiedManagerPermissions
    serializer_class = UserVerificationListSerializer
    queryset = UserVerification.objects.select_related("user").all()
    pagination_class = api_settings.DEFAULT_PAGINATION_CLASS

    def get_queryset(self):
        logger.info(
            f"UserVerificationListView: request from user {self.request.user.id}"
        )
        # Ensure related user data is prefetched for efficiency
        return super().get_queryset().order_by("-created_at")


class UserVerificationActionView(APIView):
    """
    Handle user verification actions (approve/reject).
    """

    permission_classes = VerifiedManagerPermissions

    @swagger_auto_schema(
        operation_summary="Perform Verification Action",
        operation_description="Handle user verification actions (approve/reject).",
        request_body=user_verification_action_request_body,
        responses={
            200: openapi.Response("User verification action successful."),
            400: error_response_400,
            401: error_response_401,
            403: error_response_403,
            404: error_response_404,
        },
        tags=["User Verification"],
        manual_parameters=[api_key, bearer_auth],
    )
    def post(self, request, user_id):
        return self._verification_action(request, user_id)

    def _verification_action(self, request, user_id):
        logger.info(
            f"UserVerificationActionView: request from user {request.user.id} for user {user_id}"
        )
        try:
            target_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            logger.error(f"User with id {user_id} not found.")
            raise NotFound("User not found.")
        try:
            verification = UserVerification.objects.get(user=target_user)
        except UserVerification.DoesNotExist:
            logger.error(f"User verification not found for user {target_user.id}")
            raise NotFound("User verification not found.")

        # Check if already processed
        if verification.is_approved:
            logger.warning(f"User {target_user.id} is already verified.")
            raise ValidationError("This user is already verified.")

        serializer = UserVerificationActionSerializer(
            verification, data=request.data, partial=True, context={"request": request}
        )

        if serializer.is_valid():
            # Determine action
            validated_data = serializer.validated_data
            if validated_data.get("is_approved"):
                action = "approved"
                message = "User verified successfully."
            elif validated_data.get("is_rejected"):
                action = "rejected"
                message = "User verification rejected."
            else:
                logger.error("Must specify either is_approved or is_rejected.")
                raise ValidationError("Must specify either is_approved or is_rejected.")
            with transaction.atomic():
                verification = serializer.save()

            # Invalidate caches
            cache.delete(f"user_verification_status_{target_user.id}")
            if hasattr(target_user, "candidate_profile"):
                cache.delete(f"candidate_dashboard_{target_user.candidate_profile.pk}")
            cache.delete(f"account_management_{target_user.id}")
            invalidate_all_staff_dashboards()

            user = verification.user
            base_message = f"Your verification details have been {action}.\n\n"
            footer = "Best Regards,\nManagement."
            action_content = ""
            if action == "approved" and verification.is_approved:
                action_content = (
                    'Kindly proceed to take the "Tour" of Verboheit MLC Portal.\n\n'
                )
            elif action == "rejected" and verification.is_rejected:
                action_content = (
                    "If you have any questions, please contact support.\n\n"
                )
            email_message = base_message + action_content + footer

            send_mail_task.delay(
                subject="Your User Verification Status",
                message=email_message,
                recipient_list=[user.email],
            )

            logger.info(
                "User verification %s for user %s by %s.",
                action,
                target_user.id,
                request.user.id,
            )

            return Response({"detail": message}, status=status.HTTP_200_OK)
        logger.warning(
            f"UserVerificationActionView: validation failed: {serializer.errors}"
        )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
