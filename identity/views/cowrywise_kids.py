import logging

from django.db import transaction
from rest_framework import status
from rest_framework.generics import CreateAPIView
from rest_framework.response import Response
from rest_framework.serializers import ValidationError

from core.utils.events import log_event
from identity.models import Candidate, CowrywiseKidProfile
from identity.permissions import CandidatePermissions
from identity.serializers import CowrywiseKidProfileSerializer
from competition.models import Competition, Enrollment

logger = logging.getLogger(__name__)


class CowrywiseKidProfileView(CreateAPIView):
    serializer_class = CowrywiseKidProfileSerializer
    permission_classes = CandidatePermissions

    def post(self, request, *args, **kwargs):
        logger.info(
            f"Attempting to link Cowrywise Kid profile for user: {request.user.email}"
        )

        try:
            candidate = request.user.candidate_profile
        except Candidate.DoesNotExist:
            logger.error(f"Candidate profile not found for user: {request.user.email}")
            return Response(
                {"error": "Candidate profile not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        username = request.data.get("username")
        if not username:
            logger.warning(f"No username provided by user {request.user.email}")
            return Response(
                {"error": "Username is required."}, status=status.HTTP_400_BAD_REQUEST
            )

        # Normalize username to lowercase
        username = username.lower()

        # Check if this candidate already has ANY Cowrywise Kid profile
        if hasattr(candidate, "cowrywise_kid_profile"):
            existing_profile = candidate.cowrywise_kid_profile
            logger.warning(
                f"Candidate {candidate} already has a profile linked (username: {existing_profile.username})"
            )
            return Response(
                {
                    "error": f"You have already linked a Cowrywise Kid profile with username [{existing_profile.username}]"
                },
                status=status.HTTP_409_CONFLICT,
            )

        # Check if the provided username is taken by anyone else
        if CowrywiseKidProfile.objects.filter(username=username).exists():
            logger.warning(
                f"Cowrywise username [{username}] is already taken by another candidate"
            )
            return Response(
                {
                    "error": f"The username [{username}] is already linked to another candidate"
                },
                status=status.HTTP_409_CONFLICT,
            )

        # Check for active competition and enrollment
        competition = Competition.objects.filter(
            status=Competition.Status.ACTIVE
        ).first()
        if not competition:
            logger.error(
                f"User {request.user.email} tried to link profile but no active competition exists"
            )
            return Response(
                {"error": "No active competition found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not Enrollment.objects.filter(
            competition=competition, candidate=candidate
        ).exists():
            logger.warning(
                f"User {request.user.email} is not enrolled in competition [{competition.id}]"
            )
            return Response(
                {"error": "You are not enrolled in any active competition."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Save the profile
        # We use a mutable copy of request.data to ensure the serializer sees the lowercase username
        data = request.data.copy()
        data["username"] = username
        serializer = self.get_serializer(data=data)

        with transaction.atomic():
            try:
                serializer.is_valid(raise_exception=True)
                serializer.save(candidate=candidate)
                logger.info(
                    f"Successfully linked Cowrywise Kid profile [{username}] for {request.user.email}"
                )
            except ValidationError as e:
                logger.error(f"Validation error for {request.user.email}: {e.detail}")
                return Response(
                    {"error": f"Validation error: {e.detail}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            except Exception as e:
                logger.exception(
                    f"Unexpected error linking Cowrywise profile for {request.user.email}"
                )
                return Response(
                    {"error": "An internal error occurred during profile linking."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        log_event(
            event_name="COWRYWISE_KID_REGISTRATION",
            actor=request.user,
            metadata={
                "email": candidate.user.email,
                "competition_id": competition.id,
                "username": username,
            },
        )

        return Response(
            {"detail": "Cowrywise Kid profile successfully linked"},
            status=status.HTTP_201_CREATED,
        )
