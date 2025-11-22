import os
import random
from typing import Any

import django
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Avg, Count, Sum
from django.utils import timezone

from dotenv import load_dotenv
from faker import Faker

from vmlc.models import (
    Candidate,
    CandidateAnswer,
    CandidateScore,
    CandidateScoreSnapshot,
    Exam,
    FeatureFlag,
    LeaderboardSnapshot,
    Question,
    Staff,
    User,
    UserVerification,
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

        # Clear existing data
        self.stdout.write("Clearing existing data...")
        CandidateAnswer.objects.all().delete()
        CandidateScore.objects.all().delete()
        Exam.objects.all().delete()
        Question.objects.all().delete()
        LeaderboardSnapshot.objects.all().delete()
        CandidateScoreSnapshot.objects.all().delete()

        self.stdout.write("Creating feature flags...")
        FeatureFlag.objects.get_or_create(key="candidate_registration", value=True)
        FeatureFlag.objects.get_or_create(key="staff_registration", value=True)

        # Create staff users
        self.stdout.write("Creating staff users...")
        staff_list = []
        for i in range(20):
            if User.objects.filter(email=f"staff{i+1}@mail.com").exists():
                continue
            user = User.objects.create_user(
                email=f"staff{i+1}@mail.com",
                password=os.getenv("ANON_PASSWORD"),
                first_name=fake.first_name()[:29],
                last_name=fake.last_name()[:29],
                is_email_verified=random.choice([True, False]),
                phone=generate_nigerian_phone_number(),
            )
            staff = Staff.objects.create(
                user=user,
                occupation=fake.job()[:49],
                role=random.choice(["admin", "moderator", "volunteer"]),
            )
            UserVerification.objects.create(
                user=user,
                is_approved=random.choice([True, False]),
                is_pending=random.choice([True, False]),
                is_rejected=random.choice([True, False]),
            )
            staff_list.append(staff)

        if not staff_list:
            self.stdout.write(
                "No new staff users created, fetching existing ones from the database."
            )
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
            if User.objects.filter(email=f"candidate{i+1}@mail.com").exists():
                continue
            user = User.objects.create_user(
                email=f"candidate{i+1}@mail.com",
                password=os.getenv("ANON_PASSWORD"),
                first_name=fake.first_name()[:29],
                last_name=fake.last_name()[:29],
                is_email_verified=random.choice([True, False]),
                phone=generate_nigerian_phone_number(),
            )
            candidate = Candidate.objects.create(
                user=user,
                school=fake.company()[:154] + " High",
                role=random.choice(["league", "screening"]),
            )
            UserVerification.objects.create(
                user=user,
                is_approved=random.choice([True, False]),
                is_pending=random.choice([True, False]),
                is_rejected=random.choice([True, False]),
            )
            candidate_list.append(candidate)

        if not candidate_list:
            self.stdout.write(
                "No new candidate users created, fetching existing ones from the database."
            )
            candidate_list = list(Candidate.objects.all())

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
        screening_exam = Exam.objects.create(
            stage="screening",
            level=1,
            title=fake.catch_phrase(),
            description=fake.text(),
            created_by=random.choice(staff_list),
            is_active=True,
            scheduled_date=timezone.now()
            - timezone.timedelta(days=random.randint(1, 30)),
            open_duration_hours=12,
            countdown_minutes=60,
        )
        screening_exam.questions.set(
            random.sample(question_list, k=random.randint(5, 20))
        )
        screening_exams.append(screening_exam)

        for i in range(10):
            exam = Exam.objects.create(
                stage="league",
                level=random.randint(1, 5),
                title=fake.catch_phrase(),
                description=fake.text(),
                created_by=random.choice(staff_list),
                is_active=True,
                scheduled_date=timezone.now()
                - timezone.timedelta(days=random.randint(1, 30)),
                open_duration_hours=random.randint(1, 24),
                countdown_minutes=random.randint(30, 120),
            )
            # Add a random number of questions to each exam
            exam.questions.set(random.sample(question_list, k=random.randint(5, 20)))
            league_exams.append(exam)

        # Create Candidate scores and answers
        self.stdout.write("Creating candidate scores and answers...")
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
                score = CandidateScore.objects.create(
                    candidate=candidate,
                    exam=exam,
                    score=round(random.uniform(30.0, 100.0), 2),
                )
                # Create answers for each question in the exam
                for question in exam.questions.all():
                    CandidateAnswer.objects.create(
                        candidate_score=score,
                        question=question,
                        selected_option=random.choice(["A", "B", "C", "D"]),
                    )

        # Generate Leaderboard Snapshot
        self.stdout.write("Generating leaderboard snapshot...")
        league_candidates = (
            Candidate.objects.filter(role="league", user__is_active=True)
            .annotate(total_score=Sum("scores__score"))
            .order_by("-total_score")
        )

        # Generate Candidate Score Snapshot
        self.stdout.write("Generating candidate score snapshot...")
        all_candidates = Candidate.objects.annotate(
            total_score=Sum("scores__score"),
            average_score=Avg("scores__score"),
            exams_taken=Count("scores"),
        )

        scores_data = []
        for candidate in all_candidates:
            scores_data.append(
                {
                    "candidate": MinimalCandidateSerializer(candidate).data,
                    "total_score": float(candidate.total_score or 0.0),
                    "average_score": float(candidate.average_score or 0.0),
                    "exams_taken": candidate.exams_taken or 0,
                }
            )

        CandidateScoreSnapshot.objects.create(
            data=scores_data,
            published_by=random.choice(staff_list),
            published_at=timezone.now(),
        )
        generate_leaderboard_snapshot(random.choice(staff_list).pk)

        self.stdout.write(
            self.style.SUCCESS("Database populated successfully with more data!")
        )
