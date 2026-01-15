import logging

from rest_framework import status
from rest_framework.generics import CreateAPIView
from rest_framework.response import Response
from rest_framework.serializers import ValidationError
from rest_framework.permissions import AllowAny

from vmlc.utils.helpers import sanitize_data
from vmlc.v2.serializers.support import SupportInquirySerializer

logger = logging.getLogger(__name__)

        
class SupportUsView(CreateAPIView):
    """
    API View to handle 'Support Us' inquiries.
    Authentication: x-api-key required.
    """
    permission_classes = [AllowAny]
    serializer_class = SupportInquirySerializer
    def post(self, request, *args, **kwargs):
        from vmlc.tasks import send_system_email_task

        safe_data = sanitize_data(request.data)
        logger.info(f"Support inquiry submission attempt with data: {safe_data}")

        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            support_inquiry = serializer.save()

            send_system_email_task.delay(obj_id=support_inquiry.id, is_support_inquiry=True)
            send_system_email_task.delay(obj_id=support_inquiry.id, is_support_notification=True)

            logger.info(f"Successfully registered support inquiry with email: {support_inquiry.email}")
            
            return Response(
                {
                    "status": "success",
                    "message": "Support inquiry submitted successfully."
                },
                status=status.HTTP_201_CREATED
            )
        except ValidationError as e:
            logger.warning(f"Pre-registration validation failed: {e.detail}")
            return Response(
                {
                    "status": "error",
                    "message": "Support inquiry submission failed.",
                    "errors": e.detail
                },
                status=status.HTTP_400_BAD_REQUEST
            )