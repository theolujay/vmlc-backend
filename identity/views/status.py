import logging

from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from vmlc.models import FeatureFlag

logger = logging.getLogger(__name__)


class RegistrationStatusThrottle(AnonRateThrottle):
    rate = "5000/hour"


@api_view(["GET", "HEAD"])
@permission_classes([AllowAny])
@throttle_classes([RegistrationStatusThrottle])
def registration_status(request):
    from core.utils.cache import CacheKeys, get_or_set_cache

    def fetch_reg_status():
        def _get_detailed_status(feature_flag_key):
            try:
                flag, _ = FeatureFlag.objects.get_or_create(key=feature_flag_key)
                return {"is_open": flag.value, "closing_date": flag.auto_off_date}
            except Exception as e:
                logger.error(f"Error getting feature flag {feature_flag_key}: {e}")
                return {"is_open": False, "closing_date": None}

        return {
            "candidate_registration": _get_detailed_status("candidate_registration"),
            "staff_registration": _get_detailed_status("staff_registration"),
            "support_email": settings.SUPPORT_EMAIL,
        }

    reg_status_data = get_or_set_cache(
        CacheKeys.REGISTRATION_STATUS, fetch_reg_status, ttl=604800
    )

    return Response(reg_status_data, status=status.HTTP_200_OK)
