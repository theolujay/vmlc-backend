import os
import random
from typing import Any

import django
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Avg, Count, Sum
from django.utils import timezone

from dotenv import load_dotenv
from faker import Faker

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
from vmlc.serializers.candidate import MinimalCandidateSerializer
from vmlc.utils.functions import generate_leaderboard_snapshot


load_dotenv(".env")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.docker_dev")
django.setup()


class Command(BaseCommand):
    help = "Populates the database with initial data."

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
        fake = Faker()
        Faker.seed(seed)

        def generate_nigerian_phone_number():
            # Helper to generate a valid Nigerian phone number
            prefix = random.choice(["070", "080", "081", "090", "091"])
            return f"{prefix}{random.randint(10000000, 99999999)}"

        def update_verification(user, staff_pool=None):
            statuses = [
                {"is_pending": True, "is_approved": False, "is_rejected": False},
                {"is_pending": False, "is_approved": True, "is_rejected": False},
                {"is_pending": False, "is_approved": False, "is_rejected": True},
            ]
            status_data = random.choice(statuses)

            # Check if verification already exists (created by signals?)
            verification, created = UserVerification.objects.get_or_create(
                user=user, defaults=status_data
            )
            if not created:
                for key, value in status_data.items():
                    setattr(verification, key, value)

            verification.verification_document_type = random.choice(
                ["NIN", "Passport", "School ID"]
            )

            if staff_pool and (verification.is_approved or verification.is_rejected):
                verification.action_by = random.choice(staff_pool)

            if verification.is_rejected:
                verification.rejection_reason = fake.sentence()

            verification.save()

        # Clear existing data
        self.stdout.write("Clearing existing data...")
        CandidateAnswer.objects.all().delete()
        CandidateExamResult.objects.all().delete()
        Exam.objects.all().delete()
        Question.objects.all().delete()
        LeaderboardSnapshot.objects.all().delete()
        CandidateExamResultSnapshot.objects.all().delete()
        PreRegUser.objects.all().delete()
        SupportMessage.objects.all().delete()
        SupportInquiry.objects.all().delete()
        Event.objects.all().delete()

        self.stdout.write("Creating feature flags...")
        FeatureFlag.objects.get_or_create(key="candidate_registration", value=True)
        FeatureFlag.objects.get_or_create(key="staff_registration", value=True)

        # Create staff users
        self.stdout.write("Creating staff users...")
        staff_list = []
        # We need an initial list of existing staff to act as 'created_by' or 'action_by'
        existing_staff = list(Staff.objects.all())

        for i in range(20):
            email = f"staff{i+1}@mail.com"
            if User.objects.filter(email=email).exists():
                staff = Staff.objects.filter(user__email=email).first()
                if staff:
                    staff_list.append(staff)
                continue

            user = User.objects.create_user(
                email=email,
                password=os.getenv("ANON_PASSWORD", "SecurePass123!"),
                first_name=fake.first_name()[:29],
                last_name=fake.last_name()[:29],
                is_email_verified=random.choice([True, False]),
                phone=generate_nigerian_phone_number(),
                state=random.choice(["Lagos", "Abuja", "Oyo", "Kano", "Rivers", "Edo"]),
            )

            creator = random.choice(existing_staff) if existing_staff else None

            staff = Staff.objects.create(
                user=user,
                occupation=fake.job()[:49],
                role=random.choice(["admin", "moderator", "volunteer"]),
                created_by=creator,
            )

            # Add to potential creators for subsequent iterations
            existing_staff.append(staff)
            staff_list.append(staff)

            update_verification(user, existing_staff)

        if not staff_list:
            staff_list = list(Staff.objects.all())

        if not staff_list:
            raise CommandError(
                "No staff users found or created. "
                "Please create at least one staff user before running this command."
            )

        # Create candidate users
        self.stdout.write("Creating candidate users...")
        candidate_list = []
        for i in range(100):
            email = f"candidate{i+1}@mail.com"
            if User.objects.filter(email=email).exists():
                candidate = Candidate.objects.filter(user__email=email).first()
                if candidate:
                    candidate_list.append(candidate)
                continue

            user = User.objects.create_user(
                email=email,
                password=os.getenv("ANON_PASSWORD", "password123"),
                first_name=fake.first_name()[:29],
                last_name=fake.last_name()[:29],
                is_email_verified=random.choice([True, False]),
                phone=generate_nigerian_phone_number(),
                state=random.choice(["Lagos", "Abuja", "Oyo", "Kano", "Rivers", "Edo"]),
            )
            candidate = Candidate.objects.create(
                user=user,
                school_name=fake.company()[:140] + " High",
                school_type=random.choice(["public", "private"]),
                current_class=random.choice(["SS1", "SS2", "SS3"]),
                role=random.choice(["screening", "league", "final", "winner"]),
                created_by=random.choice(staff_list),
            )

            update_verification(user, staff_list)
            candidate_list.append(candidate)

        if not candidate_list:
            candidate_list = list(Candidate.objects.all())

        # Create PreRegUsers and Funnel Events
        self.stdout.write("Creating pre-registration users and funnel events...")
        for _ in range(50):
            pre_reg = PreRegUser.objects.create(
                full_name=fake.name(),
                email=fake.email(),
                phone=generate_nigerian_phone_number(),
                interest_type=random.choice(PreRegUser.InterestType.values),
            )
            # Log pre-registration event
            Event.objects.create(
                event_name="PRE_REGISTRATION",
                metadata={"email": pre_reg.email, "interest_type": pre_reg.interest_type}
            )

        # Log conversion events for existing users to make funnel look realistic
        # Candidates
        for candidate in candidate_list[:70]:
            Event.objects.create(
                event_name="PRE_REGISTRATION",
                metadata={"email": candidate.user.email, "interest_type": "candidate"}
            )
            Event.objects.create(
                event_name="PRE_REG_CONVERSION",
                metadata={
                    "email": candidate.user.email,
                    "user_type": "candidate",
                    "interest_type": "candidate"
                }
            )
        # Volunteers
        for staff in staff_list[:15]:
            Event.objects.create(
                event_name="PRE_REGISTRATION",
                metadata={"email": staff.user.email, "interest_type": "volunteer"}
            )
            Event.objects.create(
                event_name="PRE_REG_CONVERSION",
                metadata={
                    "email": staff.user.email,
                    "user_type": "staff",
                    "interest_type": "volunteer"
                }
            )

        # Create SupportInquiries and Messages
        self.stdout.write("Creating support inquiries and conversation threads...")
        for _ in range(20):
            # 30% of inquiries are from existing users
            linked_user = None
            if random.random() < 0.3:
                linked_user = random.choice(candidate_list + staff_list).user

            inquiry = SupportInquiry.objects.create(
                user=linked_user,
                full_name=linked_user.get_full_name() if linked_user else fake.name(),
                email=linked_user.email if linked_user else fake.email(),
                phone=linked_user.phone if linked_user else generate_nigerian_phone_number(),
                support_type=random.choice(SupportInquiry.SupportType.values),
                message=fake.text(),
                organization=fake.company() if random.choice([True, False]) else "",
                consent=True,
                status=random.choice(SupportInquiry.Status.values)
            )

            # Create initial message
            SupportMessage.objects.create(
                inquiry=inquiry,
                sender=linked_user,
                sender_profile="candidate" if linked_user and hasattr(linked_user, 'candidate_profile') else ("staff" if linked_user and hasattr(linked_user, 'staff_profile') else "guest"),
                text=inquiry.message,
                is_read_by_staff=inquiry.status != "open",
                is_read_by_user=True
            )

            # Add 1-5 follow-up messages if status is not 'open'
            if inquiry.status != "open":
                for _ in range(random.randint(1, 5)):
                    is_staff_reply = random.choice([True, False])
                    # If staff reply, pick a random staff user. Otherwise user reply.
                    sender_obj = random.choice(staff_list) if is_staff_reply else linked_user
                    
                    if is_staff_reply:
                        SupportMessage.objects.create(
                            inquiry=inquiry,
                            sender=sender_obj.user,
                            sender_profile=sender_obj.role,
                            text=fake.sentence(),
                            is_read_by_staff=True,
                            is_read_by_user=random.choice([True, False])
                        )
                    elif linked_user:
                        SupportMessage.objects.create(
                            inquiry=inquiry,
                            sender=linked_user,
                            sender_profile="user",
                            text=fake.sentence(),
                            is_read_by_staff=random.choice([True, False]),
                            is_read_by_user=True
                        )

        # Create questions
        self.stdout.write("Creating questions...")
        question_list = []
        for i in range(50):
            question = Question.objects.create(
                text=fake.sentence(nb_words=10) + "?",
                option_a=fake.sentence(nb_words=3),
                option_b=fake.sentence(nb_words=3),
                option_c=fake.sentence(nb_words=3),
                option_d=fake.sentence(nb_words=3),
                correct_answer=random.choice(["A", "B", "C", "D"]),
                created_by=random.choice(staff_list),
                difficulty=random.choice(["easy", "moderate", "hard"]),
            )
            question_list.append(question)

        # Create exams
        self.stdout.write("Creating exams...")
        league_exams = []
        screening_exams = []

        # Helper for creating exams
        def create_exams(stage, count, is_screening=False):
            for _ in range(count):
                exam = Exam.objects.create(
                    stage=stage,
                    level=1 if is_screening else random.randint(1, 5),
                    title=fake.catch_phrase(),
                    description=fake.text(),
                    created_by=random.choice(staff_list),
                    is_active=True,
                    scheduled_date=timezone.now()
                    - timezone.timedelta(days=random.randint(1, 30)),
                    open_duration_hours=12 if is_screening else random.randint(1, 24),
                    countdown_minutes=60 if is_screening else random.randint(30, 120),
                )
                exam.questions.set(
                    random.sample(question_list, k=random.randint(5, 20))
                )
                if is_screening:
                    screening_exams.append(exam)
                else:
                    league_exams.append(exam)

        create_exams("screening", 3, is_screening=True)
        create_exams("league", 10, is_screening=False)

        # Create Candidate results and answers
        self.stdout.write("Creating candidate results and answers...")
        for candidate in candidate_list:
            exams_to_take = []
            if candidate.role == "screening" and screening_exams:
                exams_to_take = random.sample(
                    screening_exams, k=random.randint(1, len(screening_exams))
                )
            elif candidate.role == "league" and league_exams:
                exams_to_take = random.sample(
                    league_exams, k=random.randint(1, min(5, len(league_exams)))
                )

            for exam in exams_to_take:
                result = CandidateExamResult.objects.create(
                    candidate=candidate,
                    exam=exam,
                    score=round(random.uniform(30.0, 100.0), 2),
                    score_submitted_by=random.choice(staff_list),
                )
                # Create answers for each question in the exam
                for question in exam.questions.all():
                    CandidateAnswer.objects.create(
                        candidate_exam_result=result,
                        question=question,
                        selected_option=random.choice(["A", "B", "C", "D"]),
                    )

        # Generate Candidate Score Snapshot
        self.stdout.write("Generating candidate score snapshot...")
        all_candidates = Candidate.objects.annotate(
            total_score=Sum("results__score"),
            average_score=Avg("results__score"),
            exams_taken=Count("results"),
        )

        results_data = []
        for candidate in all_candidates:
            results_data.append(
                {
                    "candidate": MinimalCandidateSerializer(candidate).data,
                    "total_score": float(candidate.total_score or 0.0),
                    "average_score": float(candidate.average_score or 0.0),
                    "exams_taken": candidate.exams_taken or 0,
                }
            )

        CandidateExamResultSnapshot.objects.create(
            data=results_data,
            published_by=random.choice(staff_list),
            published_at=timezone.now(),
        )
        self.stdout.write("Generating leaderboard snapshot...")
        generate_leaderboard_snapshot(random.choice(staff_list).pk)

        self.stdout.write(
            self.style.SUCCESS("Database populated successfully with comprehensive test data!")
        )
