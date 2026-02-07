import logging
from datetime import datetime, timedelta
from django.utils import timezone

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
from identity.permissions import (
    ActiveModeratorPermissions,
    ActiveVolunteerPermissions,
)
from ..tasks import generate_stats_overview_task

logger = logging.getLogger(__name__)


class RegistrationStatusThrottle(AnonRateThrottle):
    rate = "5000/hour"

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
    current_time = timezone.now()
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
@api_view(["GET", "HEAD"])
@permission_classes([AllowAny])
@throttle_classes([RegistrationStatusThrottle])
def registration_status(request):
    """
    Returns information of if registration is open/closed for staff and candidate
    """
    logger.info("Registration status request by %s", request.user)
    from vmlc.v2.utils import get_or_set_cache, CacheKeys

    def fetch_reg_status():
        def _get_detailed_status(feature_flag_key):
            try:
                flag, _ = FeatureFlag.objects.get_or_create(key=feature_flag_key)
                return {
                    "is_open": flag.value,
                    "closing_date": flag.auto_off_date
                }
            except Exception as e:
                logger.error(f"Error getting feature flag {feature_flag_key}: {e}")
                return {
                    "is_open": False,
                    "closing_date": None
                }

        return {
            "candidate_registration": _get_detailed_status("candidate_registration"),
            "staff_registration": _get_detailed_status("staff_registration"),
            "support_email": settings.SUPPORT_EMAIL,
        }

    reg_status_data = get_or_set_cache(
        CacheKeys.REGISTRATION_STATUS,
        fetch_reg_status,
        ttl=604800 # 1 week
    )

    return Response(reg_status_data, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method="get",
    operation_summary="Statistics Overview",
    operation_description="Retrieve user statistics.",
    tags=["Status"],
)
@api_view(["GET"])
@permission_classes(ActiveVolunteerPermissions)
def stats_overview(request):
    """
    Retrieve overall statistics for candidates and staff.
    """
    logger.info("Stats overview request by %s", request.user.id)
    from vmlc.v2.utils import get_or_set_cache, CacheKeys
    from vmlc.utils import generate_stats_overview_data

    data = get_or_set_cache(
        CacheKeys.STATS_OVERVIEW,
        generate_stats_overview_data,
        ttl=3600
    )
    return Response(data)
