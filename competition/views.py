from rest_framework.views import APIView
from rest_framework.generics import RetrieveAPIView
from rest_framework.response import Response
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from vmlc.permissions import ActiveAdminPermissions
from vmlc.utils.swagger_schemas import api_key, bearer_auth, error_response_401, error_response_403
from competition.models import Standings
from competition.serializers import PublishStandingsSerializer, StandingsSerializer
from competition.tasks import generate_standings_task

class PublishStandingsView(APIView):
    """
    View to trigger the generation and optional publishing of standings.
    """
    permission_classes = ActiveAdminPermissions

    @swagger_auto_schema(
        operation_summary="Generate/Publish Standings",
        operation_description="Triggers async generation of standings for a specific StageExam.",
        request_body=PublishStandingsSerializer,
        responses={
            202: "Standings generation started.",
            400: "Invalid request",
            401: error_response_401,
            403: error_response_403
        },
        manual_parameters=[api_key, bearer_auth],
        tags=["Competition Leaderboard"]
    )
    def post(self, request):
        serializer = PublishStandingsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        stage_exam_id = data['stage_exam_id']
        publish_now = data['publish_now']
        
        # Pass user ID if available
        staff_id = None
        if hasattr(request.user, 'staff_profile'):
             staff_id = str(request.user.staff_profile.id)

        generate_standings_task.delay(
            stage_exam_id=str(stage_exam_id),
            publish_now=publish_now,
            staff_id=staff_id
        )
        
        return Response(
            {
                "message": "Standings generation has been started."
            },
            status=status.HTTP_202_ACCEPTED
        )


class RetrieveStandingsView(RetrieveAPIView):
    """
    View to retrieve a specific standing.
    """
    queryset = Standings.objects.prefetch_related(
        'entries',
        'entries__candidate__user'
    ).all()
    serializer_class = StandingsSerializer
    permission_classes = [ActiveAdminPermissions]
    lookup_field = 'pk'

    @swagger_auto_schema(
        operation_summary="Get Specific Standing",
        operation_description="Retrieves the details and entries of a specific standing.",
        responses={
            200: StandingsSerializer,
            401: error_response_401,
            403: error_response_403,
            404: "Not Found"
        },
        manual_parameters=[api_key, bearer_auth],
        tags=["Competition Leaderboard"]
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)