"""
Authentication-related API views for login, logout, and registration.
"""

import logging

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_api_key.permissions import HasAPIKey # type: ignore

from ..permissions import StaffWithRole
from ..models import FeatureFlag
from ..serializers import (
    CandidateRegistrationSerializer,
    StaffRegistrationSerializer,
)


logger = logging.getLogger(__name__)


class BaseRegistrationView(CreateAPIView):
    """Base registration view with common logic"""

    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return Response({"error": "Already authenticated"}, status=400)
        if not FeatureFlag.get_bool("registration_open", default=True):
            return Response(
                {"detail": "Registration is currently closed."}, status=status.HTTP_403_FORBIDDEN
            )
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": "Registration successful"},
                status=status.HTTP_201_CREATED,
            )
        return Response(
            {"error": "Registration failed", "details": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )


class CandidateRegistrationView(BaseRegistrationView):
    """Register a new candidate"""

    serializer_class = CandidateRegistrationSerializer
    permission_classes = [HasAPIKey]


class StaffRegistrationView(BaseRegistrationView):
    """Register a new staff member"""

    serializer_class = StaffRegistrationSerializer
    permission_classes = [HasAPIKey]
    
    
@api_view(["POST"])
@permission_classes([StaffWithRole(["admin", "owner"])])
def toggle_candidate_registration(request):
    """
    Toggle the candidate registration status for candidates.

    Requires staff with 'admin' or 'owner' role.
    """
    open_flag = request.data.get("open", False)
    
    obj, created = FeatureFlag.objects.get_or_create(
        key="candidate_registration_open",
        defaults={"value": open_flag}
    )

    if not created:
        obj.value = open_flag
        obj.save()
    
    return Response(
        {"message": f"candidate_registration_open: {obj.value}"}, status=status.HTTP_200_OK
    )

@api_view(["POST"])
@permission_classes([StaffWithRole(["owner"])])
def toggle_staff_registration(request):
    """
    Toggle the staff registration status for staff members.

    Requires staff with 'owner' role.
    """
    open_flag = request.data.get("open", False)

    obj, created = FeatureFlag.objects.get_or_create(
        key="staff_registration_open",
        defaults={"value": open_flag}
    )

    if not created:
        obj.value = open_flag
        obj.save()

    return Response(
        {"message": f"staff_registration_open: {obj.value}"}, status=status.HTTP_200_OK
    )

    