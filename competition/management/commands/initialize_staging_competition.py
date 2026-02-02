import logging

from django.utils import timezone
from django.db import transaction
from django.core.cache import cache
from django.core.management.base import BaseCommand
from dotenv import load_dotenv

from vmlc.models import (
    CandidateAnswer,
    CandidateExamResult,
    CandidateExamResultSnapshot,
    Exam,
    FeatureFlag,
    LeaderboardSnapshot,
    Question,
)
from competition.models import (
    Competition,
    Stage,
    StageExam,
    CandidateCompetition,
    CandidateStageProgress,
    Standings,
    StandingsEntry,
    AggregateLeaderboard,
    AggregateLeaderboardEntry,
)

load_dotenv(".env")


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Initializes the competition structure (Competition, Stages, and StageExam slots) for staging."

    def add_arguments(self, parser):
        parser.add_argument(
            "--edition",
            type=int,
            default=1,
            help="Competition edition number (e.g., 3)",
        )
        parser.add_argument(
            "--name", type=str, default="Staging Verboheit MLC", help="Competition name"
        )
        parser.add_argument(
            "--league-rounds",
            type=int,
            default=6,
            help="Number of rounds in the League stage",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be created without saving",
        )

    def handle(self, *args, **options):
        edition = options["edition"]
        name = options["name"]
        league_rounds = options["league_rounds"]
        dry_run = options["dry_run"]

        self.stdout.write(f"Setting up Competition Edition {edition}: {name}")

        if dry_run:
            self.stdout.write(
                self.style.WARNING("Dry run enabled. No changes will be saved.")
            )

        self._clear_data()
        self._create_feature_flags()
        self._create_competition_structure(
            edition=edition, name=name, league_rounds=league_rounds, dry_run=dry_run
        )
        self._clear_cache()

        self.stdout.write(
            self.style.SUCCESS("Staging environment initialized successfully")
        )

    def _clear_data(self):
        self.stdout.write("Clearing existing data...")
        Standings.objects.all().delete()
        StandingsEntry.objects.all().delete()
        AggregateLeaderboard.objects.all().delete()
        AggregateLeaderboardEntry.objects.all().delete()
        CandidateAnswer.objects.all().delete()
        CandidateExamResult.objects.all().delete()
        Exam.objects.all().delete()
        Question.objects.all().delete()
        StageExam.objects.all().delete()
        CandidateCompetition.objects.all().delete()
        CandidateStageProgress.objects.all().delete()
        Stage.objects.all().delete()
        Competition.objects.all().delete()
        LeaderboardSnapshot.objects.all().delete()
        CandidateExamResultSnapshot.objects.all().delete()

    def _create_feature_flags(self):
        FeatureFlag.objects.get_or_create(key="candidate_registration", value=True)
        FeatureFlag.objects.get_or_create(key="staff_registration", value=True)

    def _create_competition_structure(self, edition, name, league_rounds, dry_run):
        with transaction.atomic():
            # 1. Competition
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

            # 2. Stages
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

            # 3. StageExam Slots
            # Screening slot
            se, created = StageExam.objects.get_or_create(
                competition_stage=stages[Stage.Type.SCREENING],
                round=None,
                defaults={"is_active": True},
            )
            if created:
                self.stdout.write(f"    - Created Screening Exam slot")

            # League slots
            for r in range(1, league_rounds + 1):
                _, created = StageExam.objects.get_or_create(
                    competition_stage=stages[Stage.Type.LEAGUE],
                    round=r,
                    defaults={"is_active": True},
                )
                if created:
                    self.stdout.write(f"    - Created League Round {r} slot")

            # Final slot
            _, created = StageExam.objects.get_or_create(
                competition_stage=stages[Stage.Type.FINAL],
                round=None,
                defaults={"is_active": True},
            )
            if created:
                self.stdout.write(f"    - Created Final Exam slot")

            if dry_run:
                transaction.set_rollback(True)
                self.stdout.write(
                    self.style.SUCCESS("Dry run complete. No data was committed.")
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS("Staging competition setup complete.")
                )

    def _clear_cache(self):
        self.stdout.write("Clearing cache...")
        cache.clear()
