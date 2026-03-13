import logging

from django.core.paginator import Paginator
from channels.db import database_sync_to_async

from identity.permissions import StaffRoleHierarchy
from comms.models import HelpdeskThread, ThreadMessage
from comms.serializers import HelpdeskThreadListSerializer
from vmlc.utils.query_filters import (
    filter_helpdesk_threads,
    annotate_thread_with_staff_unread_count,
    annotate_thread_with_last_candidate_message_at,
    annotate_thread_with_last_message_sender_type,
)

from vmlc.utils.stats import get_helpdesk_stats_cached

logger = logging.getLogger(__name__)


class WSHelpdeskDashboardService:
    @staticmethod
    @database_sync_to_async
    def check_staff_access(user):
        """Checks if the user has staff moderator+ access."""
        if not hasattr(user, "staff_profile"):
            return False
        role = user.staff_profile.role
        return StaffRoleHierarchy.has_minimum_role(
            user_role=role, minimum_role="moderator"
        )

    @staticmethod
    @database_sync_to_async
    def get_thread_list(filters):
        """Fetches and serializes the helpdesk thread list with filters."""
        queryset = (
            HelpdeskThread.objects.select_related("candidate", "assigned_staff__user")
            .prefetch_related("messages__reads")
            .filter(messages__sender_type=ThreadMessage.SenderType.CANDIDATE)
            .distinct()
        )

        queryset = annotate_thread_with_staff_unread_count(queryset)
        queryset = annotate_thread_with_last_candidate_message_at(queryset)
        queryset = annotate_thread_with_last_message_sender_type(queryset)
        queryset = filter_helpdesk_threads(queryset, filters)

        serializer = HelpdeskThreadListSerializer(queryset, many=True)
        helpdesk_summary_data = get_helpdesk_stats_cached()

        return {
            "results": serializer.data,
            "helpdesk_summary_data": helpdesk_summary_data,
        }
