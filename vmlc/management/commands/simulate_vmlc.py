import os
import random
from typing import Any

from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.utils import timezone

from dotenv import load_dotenv
from faker import Faker

from comms.models import (
    PublicSupportRequest,
    ThreadMessage,
    Notification,
    HelpdeskThread,
)
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
from competition.services.ranking import RankingSnapshotGenerator
from competition.services.leaderboard import LeaderboardService
from competition.services.progression import ProgressionService
from competition.services.enrollment import EnrollmentService

load_dotenv(".env")


class Command(BaseCommand):
    help = "Populates the database with initial data using realistic competition flows."

    def add_arguments(self, parser):
        parser.add_argument(
            "--seed",
            type=int,
            default=random.randint(0, 1000000),
            help="Seed for random data generation to ensure reproducibility.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        seed = options["seed"]
        random.seed(seed)
        self.fake = Faker()
        Faker.seed(seed)

        self._clear_data()

        # 1. Basic Setup
        self._create_feature_flags()
        staff_list = self._create_staff(count=20)
        competition, stages = self._create_competition_structure()

        # 2. Candidates & Enrollment
        # Initially, all candidates are enrolled in Screening
        candidates = self._create_candidates(count=120, staff_pool=staff_list)
        self._enroll_candidates_in_screening(competition, candidates)

        # 3. Content
        questions = self._create_questions(count=60, staff_pool=staff_list)

        # 4. Simulation Flow
        self.stdout.write("Simulating Screening Stage...")
        screening_exam = self._create_exam(
            stage=stages["screening"],
            questions=random.sample(questions, 15),
            staff_pool=staff_list,
            days_ago=30,  # Screening happened a month ago
        )
        self._generate_exam_results(
            screening_exam, Enrollment.objects.all(), staff_list
        )
        self._finalize_ranking(screening_exam, staff_list)

        # Promote top 80 to League
        self.stdout.write("Promoting top 80 candidates to League stage...")
        ProgressionService.promote_candidates(
            from_stage_type=Stage.Type.SCREENING,
            to_stage_type=Stage.Type.LEAGUE,
            cutoff_rank=80,
            competition_id=competition.id,
        )

        self.stdout.write("Simulating League Stage (Rounds 1-6)...")
        for r in range(1, 7):
            league_exam = self._create_exam(
                stage=stages["league"],
                questions=random.sample(questions, 15),
                staff_pool=staff_list,
                days_ago=(25 - r * 3),  # Round 1: 22 days ago, Round 6: 7 days ago
                round_num=r,
            )
            # Only active enrollments take the exam
            active_parts = Enrollment.objects.filter(
                competition=competition,
                current_stage=stages["league"],
                status=Enrollment.Status.ACTIVE,
            )
            self._generate_exam_results(league_exam, active_parts, staff_list)
            self._finalize_ranking(league_exam, staff_list, update_leaderboard=True)

        # Promote top 20 to Final
        self.stdout.write("Promoting top 20 candidates to Final stage...")
        ProgressionService.promote_candidates(
            from_stage_type=Stage.Type.LEAGUE,
            to_stage_type=Stage.Type.FINAL,
            cutoff_rank=20,
            competition_id=competition.id,
        )

        self.stdout.write("Simulating Final Stage...")
        final_exam = self._create_exam(
            stage=stages["final"],
            questions=random.sample(questions, 20),
            staff_pool=staff_list,
            days_ago=3,
        )
        active_parts_final = Enrollment.objects.filter(
            competition=competition,
            current_stage=stages["final"],
            status=Enrollment.Status.ACTIVE,
        )
        self._generate_exam_results(final_exam, active_parts_final, staff_list)
        self._finalize_ranking(final_exam, staff_list)

        # 5. Ancillary Data
        self._create_pre_reg_and_events(candidates, staff_list)
        self._create_support_data(candidates, staff_list)
        self._create_candidate_notifications(candidates)
        self._clear_cache()

        self.stdout.write(self.style.SUCCESS("Database populated successfully!"))

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
        ThreadMessage.objects.all().delete()
        PublicSupportRequest.objects.all().delete()
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
            email = f"staff{i+1}@mail.com"
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

    def _create_competition_structure(self):
        self.stdout.write("Creating competition and stages...")
        competition = Competition.objects.create(
            name="Verboheit Mathematics League Competition",
            edition=1,
            start_date=timezone.now() - timezone.timedelta(days=30),
            end_date=timezone.now() + timezone.timedelta(days=60),
            status=Competition.Status.ACTIVE,
        )
        stages = {}
        for order, (st_type, st_label) in enumerate(Stage.Type.choices, start=1):
            config = {}
            if st_type == Stage.Type.SCREENING:
                config = {
                    "advancement_policy": {
                        "mode": "top_percent",
                        "value": 0.3,
                    }
                }
            else:
                config = {
                    "advancement_policy": {
                        "mode": "top_n",
                        "value": 20,
                    }
                }

            stage = Stage.objects.create(
                competition=competition,
                type=st_type,
                order=order,
                description=f"{st_label} Stage",
                config=config,
            )
            stages[st_type] = stage
        return competition, stages

    def _create_candidates(self, count, staff_pool):
        self.stdout.write(f"Creating {count} candidate users...")
        candidates = []
        for i in range(count):
            email = f"candidate{i+1}@mail.com"
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
            # self._update_verification(user, staff_pool)
            candidates.append(candidate)
        return candidates

    def _enroll_candidates_in_screening(self, competition, candidates):
        self.stdout.write("Enrolling candidates in Screening...")
        EnrollmentService.enroll_candidates(competition, candidates)

    def _create_questions(self, count, staff_pool):
        self.stdout.write(f"Creating {count} questions...")
        return [
            Question.objects.create(
                text=self.fake.sentence(nb_words=10) + "?",
                option_a=self.fake.sentence(nb_words=3),
                option_b=self.fake.sentence(nb_words=3),
                option_c=self.fake.sentence(nb_words=3),
                option_d=self.fake.sentence(nb_words=3),
                correct_answer=random.choice(["A", "B", "C", "D"]),
                created_by=random.choice(staff_pool),
                difficulty=random.choice(["easy", "moderate", "hard"]),
            )
            for _ in range(count)
        ]

    def _create_exam(self, stage, questions, staff_pool, days_ago, round_num=None):
        slot = StageExam.objects.create(competition_stage=stage, round=round_num)
        exam = Exam.objects.create(
            competition_slot=slot,
            description=self.fake.text(),
            created_by=random.choice(staff_pool),
            is_active=True,
            scheduled_date=timezone.now() - timezone.timedelta(days=days_ago),
            open_duration_hours=24,
            countdown_minutes=60,
        )
        exam.questions.set(questions)
        return exam

    def _generate_exam_results(self, exam, enrollment_pool, staff_pool):
        for enrollment in enrollment_pool:
            # Simulate some candidates missing the exam
            if random.random() < 0.05:
                continue

            result = CandidateExamResult.objects.create(
                candidate=enrollment.candidate,
                exam=exam,
                score=round(random.uniform(20.0, 100.0), 2),
                score_submitted_by=random.choice(staff_pool),
            )
            for question in exam.questions.all():
                CandidateAnswer.objects.create(
                    candidate_exam_result=result,
                    question=question,
                    selected_option=random.choice(["A", "B", "C", "D"]),
                )

    def _finalize_ranking(self, exam, staff_pool, update_leaderboard=False):
        generator = RankingSnapshotGenerator(stage_exam_id=exam.competition_slot.id)
        ranking = generator.generate_and_save_ranking(
            published_by_staff_id=random.choice(staff_pool).pk
        )
        ranking.is_published = True
        ranking.published_at = timezone.now()
        ranking.save()

        if update_leaderboard and ranking.stage == Stage.Type.LEAGUE:
            LeaderboardService.update_league_leaderboard(
                competition_id=ranking.competition_id, as_of_round=ranking.round
            )

    def _create_pre_reg_and_events(self, candidates, staff_pool):
        for _ in range(50):
            pre_reg = PreRegUser.objects.create(
                full_name=self.fake.name(),
                email=self.fake.email(),
                phone=self._generate_nigerian_phone(),
                interest_type=random.choice(PreRegUser.InterestType.values),
            )
            Event.objects.create(
                event_name="PRE_REGISTRATION",
                metadata={
                    "email": pre_reg.email,
                    "interest_type": pre_reg.interest_type,
                },
            )

    def _create_support_data(self, candidates, staff_pool):
        from comms.models import HelpdeskThread

        self.stdout.write("Creating public support requests...")
        for _ in range(10):
            PublicSupportRequest.objects.create(
                full_name=self.fake.name(),
                email=self.fake.email(),
                organization=self.fake.company(),
                phone=f"080{random.randint(10000000, 99999999)}",
                type=random.choice(PublicSupportRequest.Type.values),
                message=self.fake.paragraph(),
                consent=True,
            )

        self.stdout.write("Creating authenticated helpdesk threads...")
        for _ in range(10):
            candidate = random.choice(candidates)
            thread = HelpdeskThread.objects.create(
                candidate=candidate,
                status=random.choice(HelpdeskThread.Status.values),
                priority=random.choice(HelpdeskThread.Priority.values),
            )
            ThreadMessage.objects.create(
                thread=thread,
                sender=candidate.user,
                text=self.fake.paragraph(),
            )
            if random.random() < 0.5:
                staff = random.choice(staff_pool)
                thread.assigned_staff = staff
                thread.save()
                ThreadMessage.objects.create(
                    thread=thread,
                    sender=staff.user,
                    text=self.fake.paragraph(),
                )

    def _create_candidate_notifications(self, candidates):
        for cand in candidates[:20]:
            for _ in range(random.randint(1, 3)):
                Notification.objects.create(
                    recipient=cand.user,
                    subject=self.fake.sentence(nb_words=5),
                    message=self.fake.text(),
                    is_read=False,
                )

    def _clear_cache(self):
        self.stdout.write("Clearing cache...")
        cache.clear()
