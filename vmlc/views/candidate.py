import logging

from django.utils.decorators import method_decorator
from rest_framework.generics import ListAPIView
from rest_framework.settings import api_settings
from drf_yasg.utils import swagger_auto_schema

from identity.models import Candidate
from identity.permissions import ActiveModeratorPermissions
from ..serializers import CandidateListSerializer
from ..utils.swagger_schemas import (
    api_key,
    bearer_auth,
    candidate_list_response_schema,
    error_response_401,
    error_response_403,
)
from ..utils.query_filters import filter_candidates

logger = logging.getLogger(__name__)


@method_decorator(
    name="get",
    decorator=swagger_auto_schema(
        operation_summary="List Candidates",
        operation_description="List all candidates. Required roles: moderator or higher",
        responses={
            200: candidate_list_response_schema,
            401: error_response_401,
            403: error_response_403,
        },
        tags=["Candidates"],
        manual_parameters=[api_key, bearer_auth],
    ),
)
class CandidateListView(ListAPIView):
    """
    List all candidates.

    Accessible by staff users with roles: moderator, admin, manager, or superadmin.
    Supports pagination and query param filtering.
    """

    permission_classes = ActiveModeratorPermissions
    serializer_class = CandidateListSerializer
    pagination_class = api_settings.DEFAULT_PAGINATION_CLASS

    def get_queryset(self):
        """
        Returns a filtered queryset of candidates based on request query parameters.
        """
        logger.info(
            f"CandidateListView: request from user {self.request.user.id} with query params: {self.request.query_params}"
        )
        # Eagerly fetch related user data to prevent N+1 queries by the serializer.
        queryset = Candidate.objects.select_related("user").order_by("-created_at")
        return filter_candidates(queryset, self.request.query_params)
