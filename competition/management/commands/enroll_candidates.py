import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from competition.models import Competition, CandidateCompetition, CandidateStageProgress, Stage
from identity.models import Candidate

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Enrolls all existing candidates into the current active competition."

    def add_arguments(self, parser):
        parser.add_argument(
            "--competition-id",
            type=int,
            help="Specify a competition ID to enroll into. Defaults to the active competition.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Don't actually save changes, just show what would be done.",
        )

    def handle(self, *args, **options):
        competition_id = options.get("competition_id")
        dry_run = options.get("dry_run")

        if competition_id:
            try:
                competition = Competition.objects.get(id=competition_id)
            except Competition.DoesNotExist:
                self.stderr.write(self.style.ERROR(f"Competition with ID {competition_id} does not exist."))
                return
        else:
            competition = Competition.objects.filter(status=Competition.Status.ACTIVE).first()
            if not competition:
                self.stderr.write(self.style.ERROR("No active competition found."))
                return

        self.stdout.write(f"Target Competition: {competition} (ID: {competition.id})")

        first_stage = competition.stages.order_by("order").first()
        if not first_stage:
            self.stderr.write(self.style.ERROR(f"No stages found for competition {competition}."))
            return

        self.stdout.write(f"Enrollment Stage: {first_stage.get_type_display()}")

        # Find candidates not already in this competition
        enrolled_candidate_ids = CandidateCompetition.objects.filter(
            competition=competition
        ).values_list("candidate_id", flat=True)

        candidates_to_enroll = Candidate.objects.exclude(id__in=enrolled_candidate_ids)
        total_to_enroll = candidates_to_enroll.count()

        if total_to_enroll == 0:
            self.stdout.write(self.style.SUCCESS("All candidates are already enrolled."))
            return

        self.stdout.write(f"Found {total_to_enroll} candidates to enroll.")

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run enabled. No changes will be saved."))
            return

        with transaction.atomic():
            created_count = 0
            for candidate in candidates_to_enroll:
                # Create participation
                participation = CandidateCompetition.objects.create(
                    candidate=candidate,
                    competition=competition,
                    current_stage=first_stage,
                    status=CandidateCompetition.Status.ACTIVE
                )
                # Create progress
                CandidateStageProgress.objects.create(
                    candidate_competition=participation,
                    stage=first_stage,
                    status=CandidateStageProgress.Status.IN_PROGRESS
                )
                created_count += 1

            self.stdout.write(self.style.SUCCESS(f"Successfully enrolled {created_count} candidates."))
