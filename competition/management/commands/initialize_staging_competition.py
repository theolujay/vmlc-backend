import logging
import os
import random
from typing import Any

from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from dotenv import load_dotenv
from faker import Faker

from identity.models import (
    Candidate,
    Staff,
    User,
    UserVerification,
)
from vmlc.models import (
    CandidateAnswer,
    CandidateExamResult,
    CandidateExamResultSnapshot,
    FeatureFlag,
    LeaderboardSnapshot,
)
from competition.models import (
    Competition,
    Stage,
    Enrollment,
    EnrollmentStageProgress,
    RankingSnapshot,
    RankingSnapshotEntry,
    LeagueLeaderboard,
    LeagueLeaderboardEntry,
)
from competition.services.enrollment import EnrollmentService

load_dotenv(".env")

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Initializes the competition structure (Competition, Stages, and StageExam slots) for staging."

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
            default="Staging Verboheit MLC",
            help="Competition name",
        )
        parser.add_argument(
            "--candidates",
            type=int,
            default=10,
            help="Number of simulation candidates to create",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be created without saving",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=random.randint(0, 1000000),
            help="Seed for random data generation to ensure reproducibility.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        edition = options["edition"]
        name = options["name"]
        dry_run = options["dry_run"]
        seed = options["seed"]
        create_candidates_count = options["candidates"]

        random.seed(seed)
        self.fake = Faker()
        Faker.seed(seed)

        if dry_run:
            self.stdout.write(
                self.style.WARNING("Dry run enabled. No changes will be saved.")
            )

        with transaction.atomic():
            self._clear_data()
            self._create_feature_flags()
            competition, _ = self._create_competition_structure(edition, name)
            simulation_candidates = self._create_simulation_candidates(
                count=create_candidates_count
            )
            candidates = self._get_all_candidates()
            self._enroll_candidates_in_screening(candidates, competition)

            self.stdout.write(self.style.SUCCESS("Staging competition setup complete."))

            if dry_run:
                transaction.set_rollback(True)
                self.stdout.write(
                    self.style.SUCCESS("Dry run complete. No data was committed.")
                )
            else:
                self.stdout.write("Clearing cache...")
                cache.clear()
                self.stdout.write(
                    self.style.SUCCESS(
                        "Staging competition setup complete with simulation candidates."
                    )
                )
                self.stdout.write("Printing simulation candidates' email addresses...")
                for email in simulation_candidates:
                    self.stdout.write(f"{email}")

    def _clear_data(self):
        self.stdout.write("Clearing existing data...")
        RankingSnapshot.objects.all().delete()
        RankingSnapshotEntry.objects.all().delete()
        LeagueLeaderboard.objects.all().delete()
        LeagueLeaderboardEntry.objects.all().delete()
        CandidateAnswer.objects.all().delete()
        CandidateExamResult.objects.all().delete()
        Enrollment.objects.all().delete()
        EnrollmentStageProgress.objects.all().delete()
        LeaderboardSnapshot.objects.all().delete()
        CandidateExamResultSnapshot.objects.all().delete()

    def _generate_nigerian_phone(self):
        prefix = random.choice(["070", "080", "081", "090", "091"])
        return f"{prefix}{random.randint(10000000, 99999999)}"

    def _create_feature_flags(self):
        FeatureFlag.objects.get_or_create(key="candidate_registration", defaults={"value": True})
        FeatureFlag.objects.get_or_create(key="staff_registration", defaults={"value": True})

    def _create_competition_structure(self, edition, name):
        self.stdout.write("Creating competition and stages...")
        competition, created = Competition.objects.get_or_create(
            edition=edition,
            defaults={
                "name": name,
                "status": Competition.Status.ACTIVE,
                "start_date": timezone.now(),
            },
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created Competition: {competition}"))
        else:
            self.stdout.write(f"Competition already exists: {competition}")

        stages = {}
        stage_configs = [
            (
                Stage.Type.SCREENING,
                1,
                "One-time qualification assessment for league stage",
                {
                    "advancement_policy": {
                        "mode": "top_percent",
                        "value": 0.3,
                    },
                },
            ),
            (
                Stage.Type.LEAGUE,
                2,
                "Comprises of six assessments spread across six weeks and a leaderboard ",
                {
                    "advancement_policy": {
                        "mode": "top_n",
                        "value": 10,
                    },
                },
            ),
            (
                Stage.Type.FINAL,
                3,
                "Zenith assessment to determine top three winners",
                {
                    "advancement_policy": {
                        "mode": "top_n",
                        "value": 3,
                    },
                },
            ),
        ]

        for st_type, order, desc, config in stage_configs:
            stage, created = Stage.objects.get_or_create(
                competition=competition,
                type=st_type,
                defaults={"order": order, "description": desc, "config": config},
            )
            stages[st_type] = stage
            if created:
                self.stdout.write(f"  - Created Stage: {stage.get_type_display()}")
            else:
                self.stdout.write(
                    f"  - Stage [{stage.get_type_display()}] already exist in {str(competition)}"
                )
        return competition, stages

    def _get_all_candidates(self):
        return Candidate.objects.all()

    def _create_simulation_candidates(self, count):
        self.stdout.write(f"Creating {count} simulation candidate users...")
        simulation_candidates = list()
        for i in range(count):
            email = f"candidate{i+1}.vmlc@mailsac.com"
            if User.objects.filter(email=email).exists():
                continue

            user = User.objects.create_user(
                email=email,
                password=os.getenv("ANON_PASSWORD", "password123"),
                first_name=self.fake.first_name()[:29],
                last_name=self.fake.last_name()[:29],
                is_email_verified=True,
                phone=self._generate_nigerian_phone(),
                state=random.choice(["Lagos", "Abuja", "Rivers", "Ogun"]),
            )
            Candidate.objects.create(
                user=user,
                school_name=self.fake.company()[:140] + " High",
                school_type=random.choice(["public", "private"]),
                current_class=random.choice(["SS1", "SS2", "SS3"]),
                role="screening",
            )
            simulation_candidates.append(email)
        return simulation_candidates

    def _enroll_candidates_in_screening(self, candidates, competition):
        self.stdout.write("Enrolling candidates in Screening...")
        EnrollmentService.enroll_candidates(competition, candidates=candidates)
