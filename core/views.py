import logging

from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

logger = logging.getLogger(__name__)


@api_view(["GET", "HEAD"])
@permission_classes([AllowAny])
def health_check(request):
    current_time = timezone.now()
    logger.info("Health check performed at %s", current_time)
    return Response(
        {"status": "healthy", "timestamp": current_time.isoformat()},
        status=status.HTTP_200_OK,
    )
