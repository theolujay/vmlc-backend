import logging

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from ..models import UserVerification
from ..permissions import IsOwnerOrAdmin
from ..serializers import (
    UserVerificationSerializer,   
)

User = get_user_model()
logger = logging.getLogger(__name__)

class UserVerificationView(APIView):
    """
    Handles verification of candidates and staff members.
    - Allows candidates and staff to submit their verification data.
    - Only the user themselves or an admin can submit verification data.
    - Retrieves verification status for candidates and staff.
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    
    def _get_target_user(self, request, user_id=None):
        """Get the target user and check permissions."""
        if user_id is None or user_id == request.user.id:
            return request.user
        
        target_user = get_object_or_404(User, id=user_id)
        if not IsOwnerOrAdmin().has_object_permission(request, self, target_user):
            raise PermissionDenied("You are not authorized to this user's verification process.")
        
        return target_user

    def _get_user_verification(self, user):
        """Get or create UserVerification object and return appropriate serializer"""
        verification, created = UserVerification.objects.get_or_create(user=user)
        return verification

    def get(self, request, user_id=None):
        """Retrieve verification status for a candidate or staff member."""
        user = self._get_target_user(request, user_id)

        if not (hasattr(user, "candidate_profile") or hasattr(user, "staff_profile")):
            return Response(
                {"detail": "User doesn't have a candidate or staff profile."}, 
                status=status.HTTP_404_NOT_FOUND
            )

        verification = self._get_user_verification(user)
        serializer = UserVerificationSerializer(verification)

        return Response({"verification_data": serializer.data}, status=status.HTTP_200_OK)

    def post(self, request, user_id=None):
        """Submit verification data for a candidate or staff member."""
        user = self._get_target_user(request, user_id)
        
        # Check if user has a profile (candidate or staff)
        if not (hasattr(user, "candidate_profile") or hasattr(user, "staff_profile")):
            return Response(
                {"detail": "User doesn't have a candidate or staff profile."}, 
                status=status.HTTP_404_NOT_FOUND
            )

        verification = self._get_user_verification(user)
        
        # Check verification status
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
        
        # Process the verification data
        serializer = UserVerificationSerializer(
            verification, 
            data=request.data, 
            partial=True
        )
        
        if serializer.is_valid():
            with transaction.atomic():
                # Set as pending when submitting
                verification = serializer.save(is_pending=True)
                
            logger.info(
                "Verification data submitted for user %s by user %s.", 
                user.id, 
                request.user.id
            )
            
            return Response(
                {
                    "detail": "Verification data submitted successfully.",
                    "verification_data": UserVerificationSerializer(verification).data
                },
                status=status.HTTP_200_OK,
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def patch(self, request, user_id=None):
        """Update existing verification data (partial update)."""
        user = self._get_target_user(request, user_id)
        
        try:
            verification = UserVerification.objects.get(user=user)
        except UserVerification.DoesNotExist:
            return Response(
                {"detail": "No verification data found for this user."},
                status=status.HTTP_404_NOT_FOUND,
            )
        
        # Don't allow updates if already verified
        if verification.is_verified:
            return Response(
                {"detail": "Cannot update verification data for an already verified user."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        serializer = UserVerificationSerializer(
            verification, 
            data=request.data, 
            partial=True
        )
        
        if serializer.is_valid():
            with transaction.atomic():
                # Keep as pending or set to pending if not already
                verification = serializer.save(is_pending=True)
                
            logger.info(
                "Verification data updated for user %s by user %s.", 
                user.id, 
                request.user.id
            )
            
            return Response(
                {
                    "detail": "Verification data updated successfully.",
                    "verification_data": UserVerificationSerializer(verification).data
                },
                status=status.HTTP_200_OK,
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)