import logging

from django.core.cache import cache
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from vmlc.permissions import (
    VerifiedManagerPermissions,
    VerifiedModeratorPermissions,
)
from ..tasks import generate_stats_overview_task

logger = logging.getLogger(__name__)


@api_view(["GET"])
@permission_classes(VerifiedModeratorPermissions)
def stats_overview(request):
    """
    Retrieve overall statistics for candidates and staff.

    If the data is not cached, it triggers a background task to generate it
    and returns a message indicating that the data is being prepared.
    """
    cache_key = "stats_overview"
    cached_data = cache.get(cache_key)

    if cached_data:
        return Response(cached_data)

    # If not cached, trigger the background task
    generate_stats_overview_task.delay()

    # And return a response indicating that the data is being generated
    return Response(
        {
            "message": "Statistics overview is being generated. Please check back in a few moments."
        },
        status=status.HTTP_202_ACCEPTED,
    )
