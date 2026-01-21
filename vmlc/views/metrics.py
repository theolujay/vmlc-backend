import logging
from django.core.cache import cache
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from ..utils.metrics import get_registration_metrics, get_funnel_metrics
from ..permissions import VerifiedManagerPermissions
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
    permission_classes = VerifiedManagerPermissions

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
        
        cache_key = "registration_metrics"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return Response(cached_data)
        
        try:
            metrics_data = get_registration_metrics()
            metrics_data["funnel"] = get_funnel_metrics()
            
            # Cache for 10 minutes
            cache.set(cache_key, metrics_data, 600)
            return Response(metrics_data)
        except Exception as e:
            logger.error(f"Error computing registration metrics: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to compute registration metrics"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
