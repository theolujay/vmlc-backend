import logging


import boto3
from botocore.exceptions import ClientError
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponse
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.settings import api_settings
from channels.db import database_sync_to_async

from ..models import User, UserVerification
from ..permissions import HasStaffRole, IsObjectOwnerOrSuperAdminRole
from ..serializers import (
    UserVerificationActionSerializer,
    UserVerificationStatusSerializer,
    UserVerificationUploadSerializer,
    UserVerificationListSerializer,
)
from ..tasks import validate_user_verification_files_task
from ..utils.exceptions import PermissionDenied, NotFound, ValidationError, APIException

logger = logging.getLogger(__name__)


class UserVerificationStatusView(APIView):
    """
    Get the verification status of the authenticated user.
    """

    permission_classes = [IsAuthenticated]

    @database_sync_to_async
    def _get_user_verification_status(self, user, user_id):
        logger.info(
            f"UserVerificationStatusView: request from user {user.id} for user {user_id}"
        )
        # Determine target user
        if user_id is None:
            target_user = user
        else:
            try:
                target_user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                logger.error(f"User with id {user_id} not found.")
                raise NotFound("User not found.")
            if (
                user.id != target_user.id
                and not IsObjectOwnerOrSuperAdminRole().has_object_permission(
                    self.request, self, target_user
                )
            ):
                logger.warning(
                    f"User {user.id} does not have permission to access user {user_id}'s verification status."
                )
                raise PermissionDenied(
                    "You don't have permission to access this user's verification status."
                )

        # Check email verification first
        if not target_user.is_email_verified:
            logger.warning(f"User {target_user.id} has not verified their email.")
            return Response(
                {
                    "status": "email_not_verified",
                    "detail": "Email not verified. Verify email for user verification.",
                },
                status=status.HTTP_200_OK,
            )

        # Get or create verification record
        verification, created = UserVerification.objects.get_or_create(user=target_user)

        # Determine status based on verification record
        if verification.is_verified:
            logger.info(f"User {target_user.id} is verified.")
            return Response(
                {"status": "verified", "detail": "User is verified."},
                status=status.HTTP_200_OK,
            )

        elif verification.is_pending:
            # Return detailed verification data for pending cases
            serializer = UserVerificationStatusSerializer(verification)
            logger.info(f"User {target_user.id} has a pending verification request.")
            return Response(
                {
                    "status": "pending",
                    "detail": "Verification request is pending review.",
                    "verification_data": serializer.data,
                },
                status=status.HTTP_200_OK,
            )

        elif verification.is_rejected:
            logger.info(f"User {target_user.id} has a rejected verification request.")
            return Response(
                {
                    "status": "rejected",
                    "detail": "Verification request was rejected. You may resubmit with updated documents.",
                },
                status=status.HTTP_200_OK,
            )

        else:
            # Not verified, not pending, not rejected = never submitted
            logger.info(
                f"User {target_user.id} has not submitted a verification request."
            )
            return Response(
                {
                    "status": "not_submitted",
                    "detail": "No verification request submitted.",
                },
                status=status.HTTP_200_OK,
            )

    async def get(self, request, user_id=None):
        return await self._get_user_verification_status(request.user, user_id)


class UserVerificationUploadView(APIView):
    """
    Upload verification documents for the authenticated user.
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @database_sync_to_async
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

        if verification.is_verified:
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

            logger.info(
                "Verification data submitted by user %s. Validation is pending.",
                request.user.id,
            )
            return Response(
                {
                    "detail": "Documents uploaded successfully. Validation is in progress.",
                    "verification_data": {
                        "status": "pending_validation",
                        "has_profile_photo": bool(verification.profile_photo),
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

    async def post(self, request):
        return await self._upload_verification_documents(request)

    @database_sync_to_async
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

        if verification.is_verified:
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

            logger.info(
                "Verification data updated by user %s. Validation is pending.",
                request.user.id,
            )

            return Response(
                {
                    "detail": "Verification data updated successfully. Validation is in progress.",
                    "verification_data": {
                        "status": "pending_validation",
                        "has_profile_photo": bool(verification.profile_photo),
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

    async def patch(self, request):
        return await self._update_verification_documents(request)


import aioboto3

class UserVerificationDocumentView(APIView):
    """
    Access verification documents for authenticated user or any user (if superadmin).
    """

    permission_classes = [IsAuthenticated]

    @database_sync_to_async
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
            ) and not IsObjectOwnerOrSuperAdminRole().has_object_permission(  # Convert both to string for comparison
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
        elif file_type == "profile_photo":
            file = verification.profile_photo
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

    async def get(self, request, file_type, user_id=None):
        file, storage_prefix, target_user = await self._get_verification_document(
            request, file_type, user_id
        )

        try:
            async with aioboto3.client("s3") as s3_client:
                bucket_name = "vmlc-s3"
                object_key = f"{storage_prefix}/{file.name}"

                logger.info(f"Accessing S3: bucket='{bucket_name}', key='{object_key}'")

                # Get the object from S3
                s3_response = await s3_client.get_object(Bucket=bucket_name, Key=object_key)

                # Get content type
                content_type = s3_response.get("ContentType", "application/octet-stream")

                # Stream the content
                file_content = await s3_response["Body"].read()

                return HttpResponse(file_content, content_type=content_type)

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "NoSuchKey":
                logger.error(f"S3 object not found: {object_key}")
                raise NotFound(
                    f"The {file_type.replace('_', ' ')} file is no longer available."
                )
            elif error_code == "AccessDenied":
                logger.error(f"S3 access denied: {object_key}")
                raise PermissionDenied("Access denied to file storage.")
            else:
                logger.error(f"S3 error ({error_code}): {e}")
                raise APIException(
                    "Could not retrieve file from storage.",
                    status_code=status.HTTP_502_BAD_GATEWAY,
                )
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise APIException("Could not retrieve file from storage.")


class UserVerificationListView(ListAPIView):
    """List all verification requests for superadmin review."""

    permission_classes = [IsAuthenticated, HasStaffRole(["superadmin"])]
    serializer_class = UserVerificationListSerializer
    queryset = UserVerification.objects.select_related("user").all()
    pagination_class = api_settings.DEFAULT_PAGINATION_CLASS

    def get_queryset(self):
        logger.info(
            f"UserVerificationListView: request from user {self.request.user.id}"
        )
        # Ensure related user data is prefetched for efficiency
        return super().get_queryset().order_by("-date_created")


class UserVerificationActionView(APIView):
    """
    Handle user verification actions (approve/reject).
    """

    permission_classes = [IsAuthenticated, HasStaffRole(["superadmin"])]

    @database_sync_to_async
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
        if verification.is_verified:
            logger.warning(f"User {target_user.id} is already verified.")
            raise ValidationError("This user is already verified.")

        serializer = UserVerificationActionSerializer(
            verification, data=request.data, partial=True
        )

        if serializer.is_valid():
            # Determine action
            validated_data = serializer.validated_data
            if validated_data.get("is_verified"):
                action = "approved"
                message = "User verified successfully."
            elif validated_data.get("is_rejected"):
                action = "rejected"
                message = "User verification rejected."
            else:
                logger.error("Must specify either is_verified or is_rejected.")
                raise ValidationError("Must specify either is_verified or is_rejected.")

            with transaction.atomic():
                verification = serializer.save()

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

    async def post(self, request, user_id):
        return await self._verification_action(request, user_id)
