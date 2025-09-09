import logging


import boto3
from botocore.exceptions import ClientError
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.settings import api_settings

from ..models import User, UserVerification
from ..permissions import HasStaffRole, IsObjectOwnerOrSuperAdminRole
from ..serializers import (
    UserVerificationActionSerializer,
    UserVerificationStatusSerializer,
    UserVerificationUploadSerializer,
    UserVerificationListSerializer,
)
from ..tasks import validate_user_verification_files_task

logger = logging.getLogger(__name__)


class UserVerificationStatusView(APIView):
    """
    Get the verification status of the authenticated user.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, user_id=None):
        # Determine target user
        if user_id is None:
            target_user = request.user
        else:
            target_user = get_object_or_404(User, id=user_id)
            if (
                request.user.id != target_user.id
                and not IsObjectOwnerOrSuperAdminRole().has_object_permission(
                    request, self, target_user
                )
            ):
                raise PermissionDenied(
                    "You don't have permission to access this user's verification status."
                )

        # Check email verification first
        if not target_user.is_email_verified:
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
            return Response(
                {"status": "verified", "detail": "User is verified."},
                status=status.HTTP_200_OK,
            )

        elif verification.is_pending:
            # Return detailed verification data for pending cases
            serializer = UserVerificationStatusSerializer(verification)
            return Response(
                {
                    "status": "pending",
                    "detail": "Verification request is pending review.",
                    "verification_data": serializer.data,
                },
                status=status.HTTP_200_OK,
            )

        elif verification.is_rejected:
            return Response(
                {
                    "status": "rejected",
                    "detail": "Verification request was rejected. You may resubmit with updated documents.",
                },
                status=status.HTTP_200_OK,
            )

        else:
            # Not verified, not pending, not rejected = never submitted
            return Response(
                {
                    "status": "not_submitted",
                    "detail": "No verification request submitted.",
                },
                status=status.HTTP_200_OK,
            )


class UserVerificationUploadView(APIView):
    """
    Upload verification documents for the authenticated user.
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        verification, created = UserVerification.objects.get_or_create(
            user=request.user
        )
        if created:
            logger.info(
                "New user verification object created during upload - likely failed at email verification step prior."
            )

        # Check current status before processing
        if not verification.user.is_email_verified:
            return Response(
                {
                    "detail": "Email not verified. Please verify your email before uploading documents."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if verification.is_verified:
            return Response(
                {"detail": "This user is already verified."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if verification.is_pending:
            return Response(
                {"detail": "User already has a verification request pending."},
                status=status.HTTP_400_BAD_REQUEST,
            )

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
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request):
        """Update existing verification data (partial update)."""
        try:
            verification = UserVerification.objects.get(user=request.user)
        except UserVerification.DoesNotExist:
            return Response(
                {"detail": "No verification data found for this user."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if verification.is_verified:
            return Response(
                {
                    "detail": "Cannot update verification data for an already verified user."
                },
                status=status.HTTP_400_BAD_REQUEST,
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

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserVerificationDocumentView(APIView):
    """
    Access verification documents for authenticated user or any user (if superadmin).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, file_type, user_id=None):
        # If no user_id provided, default to current user
        if user_id is None:
            target_user = request.user
            verification = get_object_or_404(UserVerification, user=request.user)
        else:
            # user_id provided - superadmin accessing another user's files
            target_user = get_object_or_404(User, id=user_id)

            # Check permissions: only the user themselves or superadmin can access
            if str(request.user.id) != str(
                user_id
            ) and not IsObjectOwnerOrSuperAdminRole().has_object_permission(  # Convert both to string for comparison
                request, self, target_user
            ):
                raise PermissionDenied(
                    "You don't have permission to access this user's documents."
                )

            verification = get_object_or_404(UserVerification, user=target_user)

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
            return Response(
                {"detail": "Invalid file type."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not file or not file.name:
            return Response(
                {"detail": f"No {file_type.replace('_', ' ')} uploaded."},
                status=status.HTTP_404_NOT_FOUND,
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
                return Response(
                    {
                        "detail": f"The {file_type.replace('_', ' ')} file is no longer available."
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )
            elif error_code == "AccessDenied":
                logger.error(f"S3 access denied: {object_key}")
                return Response(
                    {"detail": "Access denied to file storage."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            else:
                logger.error(f"S3 error ({error_code}): {e}")
                return Response(
                    {"detail": "Could not retrieve file from storage."},
                    status=status.HTTP_502_BAD_GATEWAY,
                )
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return Response(
                {"detail": "Could not retrieve file from storage."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class UserVerificationListView(ListAPIView):
    """List all verification requests for superadmin review."""

    permission_classes = [IsAuthenticated, HasStaffRole(["superadmin"])]
    serializer_class = UserVerificationListSerializer
    queryset = UserVerification.objects.select_related("user").all()
    pagination_class = api_settings.DEFAULT_PAGINATION_CLASS

    def get_queryset(self):
        # Ensure related user data is prefetched for efficiency
        return super().get_queryset().order_by("-date_created")


class UserVerificationActionView(APIView):
    """
    Handle user verification actions (approve/reject).
    """

    permission_classes = [IsAuthenticated, HasStaffRole(["superadmin"])]

    def post(self, request, user_id):
        target_user = get_object_or_404(User, id=user_id)
        verification = get_object_or_404(UserVerification, user=target_user)

        # Check if already processed
        if verification.is_verified:
            return Response(
                {"detail": "This user is already verified."},
                status=status.HTTP_400_BAD_REQUEST,
            )

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
                return Response(
                    {"detail": "Must specify either is_verified or is_rejected."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            with transaction.atomic():
                verification = serializer.save()

            logger.info(
                "User verification %s for user %s by %s.",
                action,
                target_user.id,
                request.user.id,
            )

            return Response({"detail": message}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
