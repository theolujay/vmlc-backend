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

logger = logging.getLogger(__name__)

class WSHelpdeskDashboardService:
    @staticmethod
    @database_sync_to_async
    def check_staff_access(user):
        """Checks if the user has staff moderator+ access."""
        if not hasattr(user, "staff_profile"):
            return False
        role = user.staff_profile.role
        return StaffRoleHierarchy.has_minimum_role(user_role=role, minimum_role="moderator")

    @staticmethod
    @database_sync_to_async
    def get_thread_list(page_number, filters):
        """Fetches and serializes the helpdesk thread list with filters and pagination."""
        queryset = HelpdeskThread.objects.select_related(
            "candidate", "assigned_staff__user"
        ).prefetch_related("messages__reads").filter(
            messages__sender_type=ThreadMessage.SenderType.CANDIDATE
        ).distinct()

        queryset = annotate_thread_with_staff_unread_count(queryset)
        queryset = annotate_thread_with_last_candidate_message_at(queryset)
        queryset = annotate_thread_with_last_message_sender_type(queryset)
        queryset = filter_helpdesk_threads(queryset, filters)

        paginator = Paginator(queryset, 20)
        page = paginator.get_page(page_number)
        serializer = HelpdeskThreadListSerializer(page, many=True)

        return {
            "results": serializer.data,
            "pagination": {
                "count": paginator.count,
                "page": page.number,
                "page_size": paginator.per_page,
                "total_pages": paginator.num_pages,
                "has_next": page.has_next(),
                "has_previous": page.has_previous(),
            },
        }
