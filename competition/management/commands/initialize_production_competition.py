import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from competition.models import (
    Competition,
    Stage,
    CandidateCompetition,
    CandidateStageProgress,
)
from identity.models import Candidate
from vmlc.models import FeatureFlag

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Initializes the competition structure (Competition, Stages, and StageExam slots) for production."

    def add_arguments(self, parser):
        parser.add_argument(
            "--edition",
            type=int,
            default=3,
            help="Competition edition number (e.g., 3)",
        )
        parser.add_argument(
            "--name",
            type=str,
            default="Verboheit Mathematics League Competition",
            help="Competition name",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be created without saving",
        )

    def handle(self, *args, **options):
        edition = options["edition"]
        name = options["name"]
        dry_run = options["dry_run"]

        self.stdout.write(f"Setting up Competition Edition {edition}: {name}")

        if dry_run:
            self.stdout.write(
                self.style.WARNING("Dry run enabled. No changes will be saved.")
            )

        with transaction.atomic():
            # Competition
            competition, created = Competition.objects.get_or_create(
                edition=edition,
                defaults={
                    "name": name,
                    "status": Competition.Status.ACTIVE,
                    "start_date": timezone.now(),
                },
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f"Created Competition: {competition}")
                )
            else:
                self.stdout.write(f"Competition already exists: {competition}")

            # Stages
            stage_configs = [
                (
                    Stage.Type.SCREENING,
                    1,
                    "One-time qualification assessment for league stage",
                    {"promotion_cutoff": 80},
                ),
                (
                    Stage.Type.LEAGUE,
                    2,
                    "Comprises of six assessments spread across six weeks and a leaderboard ",
                    {"promotion_cutoff": 20},
                ),
                (
                    Stage.Type.FINAL,
                    3,
                    "Zenith assessment to determine top three winners",
                    {"promotion_cutoff": 3},
                ),
            ]

            stages = {}
            for st_type, order, desc, config in stage_configs:
                stage, created = Stage.objects.get_or_create(
                    competition=competition,
                    type=st_type,
                    defaults={"order": order, "description": desc, "config": config},
                )
                stages[st_type] = stage
                if created:
                    self.stdout.write(f"  - Created Stage: {stage.get_type_display()}")
          
            # Feature Flags
            FeatureFlag.objects.get_or_create(
                key="candidate_registration", defaults={"value": True}
            )
            FeatureFlag.objects.get_or_create(
                key="staff_registration", defaults={"value": True}
            )

            # Enroll Candidates
            self.stdout.write("Enrolling candidates...")

            first_stage = competition.stages.order_by("order").first()
            if not first_stage:
                self.stderr.write(
                    self.style.ERROR(f"No stages found for competition {competition}.")
                )
            else:
                self.stdout.write(f"Enrollment Stage: {first_stage.get_type_display()}")

                # Find candidates not already in this competition
                enrolled_candidate_ids = CandidateCompetition.objects.filter(
                    competition=competition
                ).values_list("candidate_id", flat=True)

                candidates_to_enroll = Candidate.objects.exclude(
                    pk__in=enrolled_candidate_ids
                )
                total_to_enroll = candidates_to_enroll.count()

                if total_to_enroll == 0:
                    self.stdout.write(
                        self.style.SUCCESS("All candidates are already enrolled.")
                    )
                else:
                    self.stdout.write(f"Found {total_to_enroll} candidates to enroll.")
                    created_count = 0
                    for candidate in candidates_to_enroll:
                        # Create participation
                        participation = CandidateCompetition.objects.create(
                            candidate=candidate,
                            competition=competition,
                            current_stage=first_stage,
                            status=CandidateCompetition.Status.ACTIVE,
                        )
                        # Create progress
                        CandidateStageProgress.objects.create(
                            candidate_competition=participation,
                            stage=first_stage,
                            status=CandidateStageProgress.Status.IN_PROGRESS,
                        )
                        created_count += 1

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Successfully enrolled {created_count} candidates."
                        )
                    )

            if dry_run:
                transaction.set_rollback(True)
                self.stdout.write(
                    self.style.SUCCESS("Dry run complete. No data was committed.")
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS("Production competition setup complete.")
                )
