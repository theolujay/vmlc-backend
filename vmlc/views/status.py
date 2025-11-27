import logging
from datetime import datetime, timezone

from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle

from django.conf import settings
from django.core.cache import cache
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from vmlc.models import FeatureFlag
from vmlc.permissions import (
    VerifiedModeratorPermissions,
)
from ..tasks import generate_stats_overview_task

logger = logging.getLogger(__name__)

class RegistrationStatusThrottle(AnonRateThrottle):
    rate = '1000/hour'
    
@swagger_auto_schema(
    method="get",
    operation_summary="Health Check",
    operation_description="Health check endpoint.",
    tags=["Status"],
)
@api_view(["GET", "HEAD"])
@permission_classes([AllowAny])
def health_check(request):
    """
    Returns a 200 OK response to indicate the service is healthy.
    """
    current_time = datetime.now(timezone.utc)
    logger.info("Health check performed at %s", current_time)
    return Response(
        {"status": "healthy", "timestamp": current_time.isoformat()},
        status=status.HTTP_200_OK,
    )

@swagger_auto_schema(
    method="get",
    operation_summary="Registration Status",
    operation_description="Check registration status.",
    tags=["Status"],
)
@api_view(["GET"])
@permission_classes([AllowAny])
@throttle_classes([RegistrationStatusThrottle])
def registration_status(request):
    """
    Returns information of if registration is open/closed for staff and candidate
    """
    logger.info("Registration status request by %s", request.user)
    cache_key = "registration_status"
    cached_data = cache.get(cache_key)
    
    if cached_data:
        return Response(cached_data, status=status.HTTP_200_OK)
    is_candidate_reg_open: bool = FeatureFlag.get_bool("candidate_registration")
    is_staff_reg_open: bool = FeatureFlag.get_bool("staff_registration")

    reg_status = {
        "is_candidate_reg_open": is_candidate_reg_open,
        "is_staff_reg_open": is_staff_reg_open,
        "support_email": settings.SUPPORT_EMAIL,
    }
    cache.set(cache_key, reg_status, 300)
    
    return Response(reg_status, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method="get",
    operation_summary="Statistics Overview",
    operation_description="Retrieve user statistics.",
    tags=["Status"],
)
@api_view(["GET"])
@permission_classes(VerifiedModeratorPermissions)
def stats_overview(request):
    """
    Retrieve overall statistics for candidates and staff.

    If the data is not cached, it triggers a background task to generate it
    and returns a message indicating that the data is being prepared.
    """
    logger.info("Stats overview request by %s", request.user.id)
    cache_key = "stats_overview"
    cached_data = cache.get(cache_key)

    if cached_data:
        return Response(cached_data)

    generate_stats_overview_task.delay()

    return Response(
        {
            "message": "Statistics overview is being generated. Please check back in a few moments."
        },
        status=status.HTTP_202_ACCEPTED,
    )
