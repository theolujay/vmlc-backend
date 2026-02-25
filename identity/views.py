import logging

from django.db import transaction
from rest_framework import status
from rest_framework.generics import CreateAPIView
from rest_framework.response import Response
from rest_framework.serializers import ValidationError

from vmlc.utils.events import log_event
from identity.models import Candidate, CowrywiseKidProfile
from identity.permissions import CandidatePermissions
from identity.serializers import CowrywiseKidProfileSerializer
from competition.models import Competition, Enrollment

logger = logging.getLogger(__name__)


class CowrywiseKidProfileView(CreateAPIView):
    serializer_class = CowrywiseKidProfileSerializer
    permission_classes = CandidatePermissions

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            candidate = Candidate.objects.get(user=request.user)
            username = request.data.get("username")
            cowrywise_kid_profile = CowrywiseKidProfile.objects.filter(
                candidate=candidate,
                username=username
            )
            if cowrywise_kid_profile.exists():
                return Response(
                    {
                        "detail": f"This Cowrywise Kid profile with username [{username}] is already linked"
                    },
                    status=status.HTTP_409_CONFLICT
                )
            cowrywise_kid = serializer.save(candidate=candidate)

        except Candidate.DoesNotExist:
            return Response({"error": "Candidate profile not found."}, status=status.HTTP_404_NOT_FOUND)
        except ValidationError as e:
            return Response({"error": f"Validation error: {e}"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            competition = Competition.objects.filter(status=Competition.Status.ACTIVE).first()
            if not competition:
                return Response({"error": "No active competition found."}, status=status.HTTP_404_NOT_FOUND)

            candidate_enrollment = Enrollment.objects.get(competition=competition, candidate=cowrywise_kid.candidate)
            log_event(
                event_name="COWRYWISE_KID_REGISTRATION",
                metadata={
                    "email": candidate_enrollment.candidate.user.email,
                    "competition_id": competition.id,
                }
            )
        except Enrollment.DoesNotExist:
            return Response({"error": "You are not enrolled in any competition."}, status=status.HTTP_403_FORBIDDEN)

        return Response(
            {
                "detail": "Cowrywise Kid profile successfully linked"
            },
            status=status.HTTP_201_CREATED
        )