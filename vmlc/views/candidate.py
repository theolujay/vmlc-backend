import logging

from rest_framework.generics import ListAPIView
from rest_framework.settings import api_settings

from identity.models import Candidate
from identity.permissions import ActiveModeratorPermissions
from ..serializers import CandidateListSerializer
from ..utils.query_filters import filter_candidates

logger = logging.getLogger(__name__)


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
