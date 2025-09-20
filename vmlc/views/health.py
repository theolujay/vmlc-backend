import logging
from datetime import datetime, timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status


logger = logging.getLogger(__name__)


@api_view(["GET"])
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
