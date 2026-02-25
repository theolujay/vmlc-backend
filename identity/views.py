import logging

from rest_framework import status
from rest_framework.generics import CreateAPIView
from rest_framework.response import Response
from rest_framework.serializers import ValidationError

from identity.models import Candidate
from identity.permissions import CandidatePermissions, ActiveModeratorPermissions
from identity.serializers import CowrywiseKidProfileSerializer
from competition.models import Competition, Enrollment

class CowrywiseKidProfileView(CreateAPIView):
    serializer_class = CowrywiseKidProfileSerializer
    permission_classes = CandidatePermissions

    def post(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            candidate = Candidate.objects.get(user=request.user)
            cowrywise_kid = serializer.save(candidate=candidate)
        except ValidationError as e:
            return Response({"error": f"Validation error: {e}"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            competition = Competition.objects.filter(status=Competition.Status.ACTIVE).first()

            candidate_enrollment = Enrollment.objects.get(competition=competition, candidate=cowrywise_kid.candidate)
            from vmlc.utils.events import log_event
            log_event(
                event_name="COWRYWISE_KID_REGISTRATION",
                metadata={
                    "email": candidate_enrollment.candidate.user.email,
                    "competition_id": competition.id,
                }
            )
        except Enrollment.DoesNotExist:
            return Response({"error": "You are not enrolled in any competition."}, status=status.HTTP_403_FORBIDDEN)

        return Response(serializer.data, status=status.HTTP_201_CREATED)
