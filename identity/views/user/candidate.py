import logging

from rest_framework.generics import ListAPIView
from rest_framework.settings import api_settings

from core.utils.query_filters import filter_candidates
from identity.models import Candidate
from identity.permissions import ActiveModeratorPermissions
from identity.serializers import CandidateListSerializer

logger = logging.getLogger(__name__)


class CandidateListView(ListAPIView):
    permission_classes = ActiveModeratorPermissions
    serializer_class = CandidateListSerializer
    pagination_class = api_settings.DEFAULT_PAGINATION_CLASS

    def get_queryset(self):
        logger.info(
            f"CandidateListView: request from user {self.request.user.id} with query params: {self.request.query_params}"
        )
        queryset = Candidate.objects.select_related("user").order_by("-created_at")
        return filter_candidates(queryset, self.request.query_params)
