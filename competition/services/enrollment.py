import logging
from django.db import transaction
from competition.models import (
    Competition,
    Enrollment,
    EnrollmentStageProgress,
)
from identity.models import Candidate

logger = logging.getLogger(__name__)


class EnrollmentError(Exception):
    pass


class EnrollmentService:
    """
    Service to handle candidate enrollment into competitions.
    """

    @staticmethod
    @transaction.atomic
    def enroll_candidates(competition, candidates=None):
        """
        Enrolls candidates into the first stage of a competition.
        If candidates is None, enrolls all candidates not already in the competition.
        """
        first_stage = competition.stages.order_by("order").first()
        if not first_stage:
            raise EnrollmentError(f"No stages found for competition {competition}.")

        if candidates is None:
            # Find candidates not already in this competition
            enrolled_candidate_ids = Enrollment.objects.filter(
                competition=competition
            ).values_list("candidate_id", flat=True)
            candidates = Candidate.objects.exclude(pk__in=enrolled_candidate_ids)

        total_to_enroll = (
            candidates.count() if hasattr(candidates, "count") else len(candidates)
        )
        if total_to_enroll == 0:
            return 0

        created_count = 0
        for candidate in candidates:
            # Create enrollment
            enrollment, created = Enrollment.objects.get_or_create(
                candidate=candidate,
                competition=competition,
                defaults={
                    "current_stage": first_stage,
                    "status": Enrollment.Status.ACTIVE,
                },
            )

            if created:
                # Create progress
                EnrollmentStageProgress.objects.get_or_create(
                    enrollment=enrollment,
                    stage=first_stage,
                    defaults={
                        "status": EnrollmentStageProgress.Status.IN_PROGRESS,
                    },
                )
                created_count += 1
            else:
                # If enrollment already exists, ensure it's active and on the right stage if needed?
                # Actually, the requirement from enroll_candidates.py was to enroll those NOT already enrolled.
                # So get_or_create is safer if we passed a specific list.
                pass

        return created_count
