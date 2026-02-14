import logging
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from identity.permissions import HasXAPIKey
from vmlc.services.exam_access import ExamAccessService
from vmlc.utils.helpers import sanitize_data

logger = logging.getLogger(__name__)

class DirectAccessLoginView(APIView):
    """
    Login via a unique single-use passcode for direct exam access.
    """
    permission_classes = [HasXAPIKey]

    def post(self, request):
        safe_data = sanitize_data(request.data)
        passcode = request.data.get('passcode')

        if not passcode:
            return Response({'detail': 'Passcode is required.'}, status=status.HTTP_400_BAD_REQUEST)

        logger.info(f"Direct access login attempt with passcode: {passcode[:8]}...")

        data, error = ExamAccessService.authenticate_passcode(passcode)

        if error:
            logger.warning(f"Direct access login failed: {error}")
            return Response({'detail': error}, status=status.HTTP_403_FORBIDDEN)

        logger.info(f"Direct access login successful for user {data["profile"]["user"]["email"]}")
        return Response(data, status=status.HTTP_200_OK)
