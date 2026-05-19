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

from competition.models import (
    Competition,
    Enrollment,
    EnrollmentStageProgress,
    LeagueLeaderboard,
    LeagueLeaderboardEntry,
    RankingSnapshot,
    RankingSnapshotEntry,
    Stage,
    StageExam,
)
from competition.services.enrollment import EnrollmentService
from identity.models import (
    Candidate,
    Staff,
    User,
    UserVerification,
)
from vmlc.models import (
    CandidateAnswer,
    CandidateExamResult,
    Exam,
    FeatureFlag,
    Question,
)

load_dotenv(".env")

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Initializes the competition structure (Competition, Stages, and StageExam slots) for development."

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
            default="Development Verboheit MLC",
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

            staff_list = self._create_staff(count=5)
            questions = self._create_questions(count=50, staff_pool=staff_list)

            competition, stages = self._create_competition_structure(edition, name)
            self._create_exams(stages, questions, staff_list)

            simulation_candidates = self._create_simulation_candidates(
                count=create_candidates_count
            )
            candidates = self._get_all_candidates()
            self._enroll_candidates_in_screening(candidates, competition)

            self.stdout.write(
                self.style.SUCCESS("Development competition setup complete.")
            )

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
                        "Development competition setup complete with simulation candidates."
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
        Exam.objects.all().delete()
        StageExam.objects.all().delete()
        Question.objects.all().delete()
        Enrollment.objects.all().delete()
        EnrollmentStageProgress.objects.all().delete()

    def _generate_nigerian_phone(self):
        prefix = random.choice(["070", "080", "081", "090", "091"])
        return f"{prefix}{random.randint(10000000, 99999999)}"

    def _create_feature_flags(self):
        FeatureFlag.objects.get_or_create(
            key="candidate_registration", defaults={"value": True}
        )
        FeatureFlag.objects.get_or_create(
            key="staff_registration", defaults={"value": True}
        )

    def _update_verification(self, user, staff_pool=None):
        statuses = [
            {"is_pending": True, "is_approved": False, "is_rejected": False},
            {"is_pending": False, "is_approved": True, "is_rejected": False},
            {"is_pending": False, "is_approved": False, "is_rejected": True},
        ]
        status_data = random.choice(statuses)
        verification, _ = UserVerification.objects.get_or_create(
            user=user, defaults=status_data
        )
        verification.verification_document_type = random.choice(
            ["NIN", "Passport", "School ID"]
        )
        if staff_pool and (verification.is_approved or verification.is_rejected):
            verification.action_by = random.choice(staff_pool)
        if verification.is_rejected:
            verification.rejection_reason = self.fake.sentence()
        verification.save()

    def _create_staff(self, count):
        self.stdout.write(f"Creating {count} staff users...")
        staff_list = []
        for i in range(count):
            email = f"staff{i + 1}@dev.mail.com"
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

    def _create_questions(self, count, staff_pool):
        self.stdout.write(f"Creating {count} questions...")
        questions = []
        for i in range(count):
            question = Question.objects.create(
                text=self.fake.sentence(nb_words=10) + "?",
                option_a=self.fake.sentence(nb_words=3),
                option_b=self.fake.sentence(nb_words=3),
                option_c=self.fake.sentence(nb_words=3),
                option_d=self.fake.sentence(nb_words=3),
                correct_answer=random.choice(["A", "B", "C", "D"]),
                created_by=random.choice(staff_pool) if staff_pool else None,
                difficulty=random.choice(["easy", "moderate", "hard"]),
            )
            questions.append(question)
        return questions

    def _create_competition_structure(self, edition, name):
        self.stdout.write("Creating competition and stages...")

        competition = Competition.objects.filter(
            status=Competition.Status.ACTIVE
        ).first()
        if not competition:
            self.stderr.write(
                self.style.ERROR("No active competition found. Creating one...")
            )

            competition, created = Competition.objects.get_or_create(
                name=name,
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
            else:
                self.stdout.write(
                    f"  - Stage [{stage.get_type_display()}] already exist in {str(competition)}"
                )
        return competition, stages

    def _create_exams(self, stages, questions, staff_pool):
        self.stdout.write("Creating exams...")
        # Screening
        screening_stage = stages[Stage.Type.SCREENING]
        self._create_single_exam(
            screening_stage, questions, staff_pool, "Screening Exam"
        )

        # League (6 rounds)
        league_stage = stages[Stage.Type.LEAGUE]
        for i in range(1, 7):
            self._create_single_exam(
                league_stage, questions, staff_pool, f"League Round {i}", round_num=i
            )

        # Final
        final_stage = stages[Stage.Type.FINAL]
        self._create_single_exam(final_stage, questions, staff_pool, "Final Exam")

    def _create_single_exam(
        self, stage, questions, staff_pool, description, round_num=None
    ):
        slot, _ = StageExam.objects.get_or_create(
            competition_stage=stage, round=round_num
        )
        # Check if exam exists for slot
        if hasattr(slot, "exam"):
            return slot.exam

        exam = Exam.objects.create(
            competition_slot=slot,
            description=description,
            created_by=random.choice(staff_pool) if staff_pool else None,
            is_active=True,
            # Set to active now so candidates can take it immediately in dev
            scheduled_date=timezone.now(),
            open_duration_hours=1,
            countdown_minutes=5,
        )
        if questions:
            exam.questions.set(random.sample(questions, k=min(len(questions), 15)))
        return exam

    def _get_all_candidates(self):
        return Candidate.objects.all()

    def _create_simulation_candidates(self, count):
        self.stdout.write(f"Creating {count} simulation candidate users...")
        simulation_candidates = list()
        for i in range(count):
            email = f"candidate{i + 1}.vmlc@mailsac.com"
            user = None
            if User.objects.filter(email=email).exists():
                candidate = Candidate.objects.filter(user__email=email).first()
                if candidate:
                    simulation_candidates.append(email)
                    continue
                user = User.objects.get(email=email)

            else:
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
        try:
            from competition.services.enrollment import EnrollmentError

            created_count = EnrollmentService.enroll_candidates(
                competition, candidates=candidates
            )
            if created_count == 0:
                self.stdout.write(
                    self.style.SUCCESS("All candidates are already enrolled.")
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Successfully enrolled {created_count} candidates."
                    )
                )
        except EnrollmentError as e:
            self.stderr.write(self.style.ERROR(f"Enrollment failed: {str(e)}"))
