import logging
import os
import random
from typing import Any, List, Dict

from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from dotenv import load_dotenv
from faker import Faker

from comms.models import Notification
from identity.models import (
    Candidate,
    PreRegUser,
    Staff,
    User,
    UserVerification,
)
from vmlc.models import (
    CandidateAnswer,
    CandidateExamResult,
    CandidateExamResultSnapshot,
    Exam,
    FeatureFlag,
    LeaderboardSnapshot,
    Question,
    SupportInquiry,
    SupportMessage,
    Event,
)
from competition.models import (
    Competition,
    Stage,
    StageExam,
    Enrollment,
    EnrollmentStageProgress,
    RankingSnapshot,
    RankingSnapshotEntry,
    LeagueLeaderboard,
    LeagueLeaderboardEntry,
)

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
            staff_list = self._create_staff(count=5)
            competition, stages = self._create_competition_structure(edition, name)
            candidates = self._create_candidates(count=50, staff_pool=staff_list)
            self._enroll_candidates_in_screening(candidates, competition, stages[Stage.Type.SCREENING])

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
                    self.style.SUCCESS("Staging competition setup complete.")
                )
        
    def _clear_data(self):
        self.stdout.write("Clearing existing data...")
        RankingSnapshot.objects.all().delete()
        RankingSnapshotEntry.objects.all().delete()
        LeagueLeaderboard.objects.all().delete()
        LeagueLeaderboardEntry.objects.all().delete()
        CandidateAnswer.objects.all().delete()
        CandidateExamResult.objects.all().delete()
        Exam.objects.all().delete()
        Question.objects.all().delete()
        StageExam.objects.all().delete()
        Enrollment.objects.all().delete()
        EnrollmentStageProgress.objects.all().delete()
        Stage.objects.all().delete()
        Competition.objects.all().delete()
        LeaderboardSnapshot.objects.all().delete()
        CandidateExamResultSnapshot.objects.all().delete()
        PreRegUser.objects.all().delete()
        SupportMessage.objects.all().delete()
        SupportInquiry.objects.all().delete()
        Event.objects.all().delete()
        Notification.objects.all().delete()

    def _generate_nigerian_phone(self):
        prefix = random.choice(["070", "080", "081", "090", "091"])
        return f"{prefix}{random.randint(10000000, 99999999)}"

    def _create_feature_flags(self):
        FeatureFlag.objects.get_or_create(key="candidate_registration", value=True)
        FeatureFlag.objects.get_or_create(key="staff_registration", value=True)

    def _update_verification(self, user, staff_pool=None):
        statuses = [
            {"is_pending": True, "is_approved": False, "is_rejected": False},
            {"is_pending": False, "is_approved": True, "is_rejected": False},
            {"is_pending": False, "is_approved": False, "is_rejected": True},
        ]
        status_data = random.choice(statuses)
        verification, _ = UserVerification.objects.get_or_create(user=user, defaults=status_data)
        verification.verification_document_type = random.choice(["NIN", "Passport", "School ID"])
        if staff_pool and (verification.is_approved or verification.is_rejected):
            verification.action_by = random.choice(staff_pool)
        if verification.is_rejected:
            verification.rejection_reason = self.fake.sentence()
        verification.save()

    def _create_staff(self, count):
        self.stdout.write(f"Creating {count} staff users...")
        staff_list = []
        for i in range(count):
            email = f"staff{i+1}@staging.mail.com" # Use staging-specific email
            if User.objects.filter(email=email).exists():
                staff = Staff.objects.filter(user__email=email).first()
                if staff:
                    staff_list.append(staff)
                continue

            user = User.objects.create_user(
                email=email,
                password=os.getenv("ANON_PASSWORD", "SecurePass123!"),
                first_name=self.fake.first_name()[:29],
                last_name=self.fake.last_name()[:29],
                is_email_verified=random.choice([True, False]),
                phone=self._generate_nigerian_phone(),
                state=random.choice(["Lagos", "Abuja", "Oyo", "Kano", "Rivers", "Edo"]),
            )

            staff = Staff.objects.create(
                user=user,
                occupation=self.fake.job()[:49],
                role=random.choice(["admin", "moderator", "volunteer"]),
            )
            staff_list.append(staff)
            self._update_verification(user, staff_list)
        return staff_list

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
            self.stdout.write(
                self.style.SUCCESS(f"Created Competition: {competition}")
            )
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
        return competition, stages

    def _create_candidates(self, count, staff_pool):
        self.stdout.write(f"Creating {count} candidate users...")
        candidates = []
        for i in range(count):
            email = f"candidate{i+1}@staging.mail.com" # Use staging-specific email
            if User.objects.filter(email=email).exists():
                candidate = Candidate.objects.filter(user__email=email).first()
                if candidate:
                    candidates.append(candidate)
                continue

            user = User.objects.create_user(
                email=email,
                password=os.getenv("ANON_PASSWORD", "password123"),
                first_name=self.fake.first_name()[:29],
                last_name=self.fake.last_name()[:29],
                is_email_verified=random.choice([True, False]),
                phone=self._generate_nigerian_phone(),
                state=random.choice(["Lagos", "Abuja", "Oyo", "Kano", "Rivers", "Edo"]),
            )
            candidate = Candidate.objects.create(
                user=user,
                school_name=self.fake.company()[:140] + " High",
                school_type=random.choice(["public", "private"]),
                current_class=random.choice(["SS1", "SS2", "SS3"]),
                role=random.choice(["screening", "league", "final", "winner"]),
                created_by=random.choice(staff_pool),
            )
            # self._update_verification(user, staff_pool) # Verification is not strictly needed for basic staging UI testing
            candidates.append(candidate)
        return candidates

    def _enroll_candidates_in_screening(self, candidates, competition, first_stage):
        self.stdout.write("Enrolling candidates in Screening...")
        for cand in candidates:
            enrollment = Enrollment.objects.create(
                candidate=cand,
                competition=competition,
                current_stage=first_stage,
                status=Enrollment.Status.ACTIVE
            )
            EnrollmentStageProgress.objects.create(
                enrollment=enrollment,
                stage=first_stage,
                status=EnrollmentStageProgress.Status.IN_PROGRESS
            )
