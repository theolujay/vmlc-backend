import logging
import boto3
from botocore.exceptions import ClientError

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect, Http404

from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from ..models import UserVerification
from ..permissions import IsObjectOwnerOrSuperAdminRole, HasStaffRole
from ..serializers import (
    UserVerificationStatusSerializer,
    UserVerificationUploadSerializer,
)

User = get_user_model()
logger = logging.getLogger(__name__)


class UserVerificationStatusView(APIView):
    """
    Get the verification status of the authenticated user.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        verification, created = UserVerification.objects.get_or_create(
            user=request.user
        )
        serializer = UserVerificationStatusSerializer(verification)
        return Response(serializer.data)


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
        if verification.is_verified:
            return Response(
                {"detail": "This user has already been verified."},
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
                # Set as pending when submitting
                verification = serializer.save(is_pending=True)

            logger.info("Verification data submitted by user %s.", request.user.id)
            return Response(
                {"detail": "Documents uploaded successfully."},
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request):
        """Update existing verification data (partial update)."""
        try:
            verification = UserVerification.objects.get(user=request.user.id)
        except UserVerification.DoesNotExist:
            return Response(
                {"detail": "NO verification data found for this user."},
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
                # keep as pending or set to pending if not already
                verification = serializer.save(is_pending=True)

                logger.info("Verfication data updated by user %s.", request.user.id)

                return Response(
                    {
                        "detail": "Verification data updated successfully.",
                        "verification_data": UserVerificationUploadSerializer(
                            verification
                        ).data,
                    },
                    status=status.HTTP_200_OK,
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
            if (
                request.user.id != target_user.id
                and not IsObjectOwnerOrSuperAdminRole().has_object_permission(
                    request, self, target_user
                )
            ):
                raise PermissionDenied(
                    "You don't have permission to access this user's documents."
                )

            verification = get_object_or_404(UserVerification, user=target_user)

        if user_id and request.user.id != user_id:
            logger.info(
                f"Superadmin {request.user.id} accessing {file_type} for user {user_id}"
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
                {"detail": "Invalid file type."}, status=status.HTTP_400_BAD_REQUEST
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


class AdminVerificationListView(APIView):
    """List all verification requests for superadmin review."""

    permission_classes = [IsAuthenticated, HasStaffRole(["admin", "superadmin"])]

    def get(self, request):
        verifications = UserVerification.objects.select_related("user").all()

        data = []
        for verification in verifications:
            data.append(
                {
                    "user_id": verification.user.id,
                    "user_name": verification.user.get_full_name(),
                    "email": verification.user.email,
                    "is_pending": verification.is_pending,
                    "is_verified": verification.is_verified,
                    "has_profile_photo": bool(verification.profile_photo),
                    "has_id_card": bool(verification.id_card),
                    "has_verification_document": bool(
                        verification.verification_document
                    ),
                    "date_created": verification.date_created,
                }
            )

        return Response(data, status=status.HTTP_200_OK)
