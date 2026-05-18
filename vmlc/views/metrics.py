import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from ..utils.metrics import get_registration_metrics, get_funnel_metrics
from identity.permissions import ActiveVolunteerPermissions

logger = logging.getLogger(__name__)


class RegistrationMetricsView(APIView):
    """
    Retrieve aggregated registration metrics for daily and weekly trends,
    including the registration funnel.
    """

    permission_classes = ActiveVolunteerPermissions

    def get(self, request):
        logger.info(f"RegistrationMetricsView: request from user {request.user.id}")

        from vmlc.v2.utils import get_or_set_cache, CacheKeys

        query_params = request.query_params

        try:
            days = query_params.get("days")
            weeks = query_params.get("weeks")

            # Since query params can vary, we might want to include them in the cache key
            # However, the original code used a static "registration_metrics" key
            # which means it ignored query params if cached.
            # For consistency with original logic but new strategy:

            def fetch_metrics():
                kwargs = {}
                if days:
                    kwargs["days"] = int(days)
                if weeks:
                    kwargs["weeks"] = int(weeks)

                data = get_registration_metrics(**kwargs)
                data["funnel"] = get_funnel_metrics()
                return data

            metrics_data = get_or_set_cache(
                CacheKeys.REGISTRATION_METRICS, fetch_metrics, ttl=600  # 10 minutes
            )
            return Response(metrics_data)
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid query parameters for registration metrics: {str(e)}")
            return Response(
                {"error": "Invalid days or weeks parameter. Must be integers."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(
                f"Error computing registration metrics: {str(e)}", exc_info=True
            )
            return Response(
                {"error": "Failed to compute registration metrics"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
