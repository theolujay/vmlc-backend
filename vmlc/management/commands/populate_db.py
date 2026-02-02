import os
import random
from typing import Any, List, Dict

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Avg, Count, Sum
from django.utils import timezone
from django.db import transaction

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
    CandidateCompetition,
    CandidateStageProgress,
    Standings,
    StandingsEntry,
    AggregateLeaderboard,
    AggregateLeaderboardEntry,
)
from competition.services.standings import StandingsGenerator
from competition.services.leaderboard import LeaderboardService
from competition.services.progression import ProgressionService

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
        self._enroll_candidates_in_screening(candidates, competition, stages['screening'])
        
        # 3. Content
        questions = self._create_questions(count=60, staff_pool=staff_list)
        
        # 4. Simulation Flow
        self.stdout.write("Simulating Screening Stage...")
        screening_exam = self._create_exam(
            stage=stages['screening'], 
            questions=random.sample(questions, 15), 
            staff_pool=staff_list,
            days_ago=15
        )
        self._generate_exam_results(screening_exam, CandidateCompetition.objects.all(), staff_list)
        self._finalize_standings(screening_exam, staff_list)
        
        # Promote top 80 to League
        self.stdout.write("Promoting top 80 candidates to League stage...")
        ProgressionService.promote_candidates(
            from_stage_type=Stage.Type.SCREENING,
            to_stage_type=Stage.Type.LEAGUE,
            cutoff_rank=80,
            competition_id=competition.id
        )

        self.stdout.write("Simulating League Stage (Rounds 1-6)...")
        for r in range(1, 6):
            league_exam = self._create_exam(
                stage=stages['league'],
                questions=random.sample(questions, 15),
                staff_pool=staff_list,
                days_ago=(10 - r * 2),
                round_num=r
            )
            # Only active participants take the exam
            active_parts = CandidateCompetition.objects.filter(
                competition=competition, 
                current_stage=stages['league'],
                status=CandidateCompetition.Status.ACTIVE
            )
            self._generate_exam_results(league_exam, active_parts, staff_list)
            self._finalize_standings(league_exam, staff_list, update_leaderboard=True)

        # 5. Ancillary Data
        self._create_pre_reg_and_events(candidates, staff_list)
        self._create_support_data(candidates, staff_list)
        self._create_candidate_notifications(candidates)
        self._generate_legacy_snapshot(staff_list)

        self.stdout.write(self.style.SUCCESS("Database populated successfully!"))

    def _clear_data(self):
        self.stdout.write("Clearing existing data...")
        CandidateAnswer.objects.all().delete()
        CandidateExamResult.objects.all().delete()
        Exam.objects.all().delete()
        StandingsEntry.objects.all().delete()
        Standings.objects.all().delete()
        AggregateLeaderboardEntry.objects.all().delete()
        AggregateLeaderboard.objects.all().delete()
        StageExam.objects.all().delete()
        CandidateStageProgress.objects.all().delete()
        CandidateCompetition.objects.all().delete()
        Stage.objects.all().delete()
        Competition.objects.all().delete()
        Question.objects.all().delete()
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
            user = User.objects.create_user(
                email=f"staff{i+1}@mail.com",
                password=os.getenv("ANON_PASSWORD", "SecurePass123!"),
                first_name=self.fake.first_name()[:29],
                last_name=self.fake.last_name()[:29],
                is_email_verified=True,
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
            stage = Stage.objects.create(
                competition=competition,
                type=st_type,
                order=order,
                description=f"{st_label} Stage",
                config={"promotion_cutoff": 80 if st_type == "screening" else 20}
            )
            stages[st_type] = stage
        return competition, stages

    def _create_candidates(self, count, staff_pool):
        self.stdout.write(f"Creating {count} candidate users...")
        candidates = []
        for i in range(count):
            user = User.objects.create_user(
                email=f"candidate{i+1}@mail.com",
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
                role=Candidate.Roles.SCREENING,
                created_by=random.choice(staff_pool),
            )
            # self._update_verification(user, staff_pool)
            candidates.append(candidate)
        return candidates

    def _enroll_candidates_in_screening(self, candidates, competition, first_stage):
        self.stdout.write("Enrolling candidates in Screening...")
        for cand in candidates:
            participation = CandidateCompetition.objects.create(
                candidate=cand,
                competition=competition,
                current_stage=first_stage,
                status=CandidateCompetition.Status.ACTIVE
            )
            CandidateStageProgress.objects.create(
                candidate_competition=participation,
                stage=first_stage,
                status=CandidateStageProgress.Status.IN_PROGRESS
            )

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
            ) for _ in range(count)
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

    def _generate_exam_results(self, exam, participation_pool, staff_pool):
        for part in participation_pool:
            # Simulate some candidates missing the exam
            if random.random() < 0.05:
                continue
                
            result = CandidateExamResult.objects.create(
                candidate=part.candidate,
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

    def _finalize_standings(self, exam, staff_pool, update_leaderboard=False):
        generator = StandingsGenerator(stage_exam_id=exam.competition_slot.id)
        standings = generator.generate_and_save_standings(
            published_by_staff_id=random.choice(staff_pool).pk
        )
        standings.is_published = True
        standings.published_at = timezone.now()
        standings.save()
        
        if update_leaderboard and standings.stage == Stage.Type.LEAGUE:
            LeaderboardService.update_league_leaderboard(
                competition_id=standings.competition_id,
                as_of_round=standings.round
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
                metadata={"email": pre_reg.email, "interest_type": pre_reg.interest_type}
            )

    def _create_support_data(self, candidates, staff_pool):
        for _ in range(15):
            linked_user = random.choice(candidates).user if random.random() < 0.3 else None
            inquiry = SupportInquiry.objects.create(
                user=linked_user,
                full_name=linked_user.get_full_name() if linked_user else self.fake.name(),
                email=linked_user.email if linked_user else self.fake.email(),
                support_type=random.choice(SupportInquiry.SupportType.values),
                message=self.fake.text(),
                status=random.choice(SupportInquiry.Status.values)
            )
            SupportMessage.objects.create(
                inquiry=inquiry,
                sender=linked_user,
                sender_profile="candidate" if linked_user else "guest",
                text=inquiry.message
            )

    def _create_candidate_notifications(self, candidates):
        for cand in candidates[:20]:
            for _ in range(random.randint(1, 3)):
                Notification.objects.create(
                    recipient=cand.user,
                    subject=self.fake.sentence(nb_words=5),
                    message=self.fake.text(),
                    read=False
                )

    def _generate_legacy_snapshot(self, staff_list):
        # Implementation of legacy snapshot generation
        pass