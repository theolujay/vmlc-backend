import logging
from django.core.cache import cache
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from ..utils.metrics import get_registration_metrics, get_funnel_metrics
from identity.permissions import ActiveVolunteerPermissions
from ..utils.swagger_schemas import (
    api_key,
    bearer_auth,
    error_response_401,
    error_response_403,
)

logger = logging.getLogger(__name__)

class RegistrationMetricsView(APIView):
    """
    Retrieve aggregated registration metrics for daily and weekly trends, 
    including the registration funnel.
    """
    permission_classes = ActiveVolunteerPermissions

    @swagger_auto_schema(
        operation_summary="Get Registration Metrics",
        operation_description="Retrieve aggregated registration metrics for daily and weekly trends and the registration funnel.",
        manual_parameters=[api_key, bearer_auth],
        responses={
            200: openapi.Response(
                description="Registration metrics data",
                examples={
                    "application/json": {
                        "daily": {
                            "total_users": [{"day": "2023-10-01", "count": 5}],
                            "candidates": [{"day": "2023-10-01", "count": 3}],
                            "staff": [{"day": "2023-10-01", "count": 2}],
                            "pre_registrations": [{"day": "2023-10-01", "count": 10}]
                        },
                        "weekly": {
                            "total_users": [{"week": "2023-09-25", "count": 30}],
                            "candidates": [{"week": "2023-09-25", "count": 20}],
                            "staff": [{"week": "2023-09-25", "count": 10}],
                            "pre_registrations": [{"week": "2023-09-25", "count": 50}]
                        },
                        "funnel": {
                            "pre_registrations": 100,
                            "completed_registrations": 45,
                            "conversion_percentage": 45.0
                        }
                    }
                }
            ),
            401: error_response_401,
            403: error_response_403,
        },
        tags=["Metrics"],
    )
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
                CacheKeys.REGISTRATION_METRICS,
                fetch_metrics,
                ttl=600 # 10 minutes
            )
            return Response(metrics_data)
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid query parameters for registration metrics: {str(e)}")
            return Response(
                {"error": "Invalid days or weeks parameter. Must be integers."},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error computing registration metrics: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to compute registration metrics"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
