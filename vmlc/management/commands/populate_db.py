import os
import django
import random
from django.utils import timezone
from typing import Any
from faker import Faker
from dotenv import load_dotenv

load_dotenv(".env")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.docker_dev")
django.setup()

from vmlc.models import User, Candidate, Staff, Question, Exam, CandidateScore, CandidateAnswer
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Populates the database with initial data."

    def handle(self, *args: Any, **options: Any) -> None:
        fake = Faker()

        def generate_nigerian_phone_number():
            # Helper to generate a valid Nigerian phone number
            prefix = random.choice(["070", "080", "081", "090", "091"])
            return f"{prefix}{random.randint(10000000, 99999999)}"

        # Clear existing data
        CandidateAnswer.objects.all().delete()
        CandidateScore.objects.all().delete()
        Exam.objects.all().delete()
        Question.objects.all().delete()
        Staff.objects.all().delete()
        Candidate.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()

        # Create staff users
        staff_list = []
        for i in range(20):
            user = User.objects.create_user(
                email=f"staff{i+1}@mail.com",
                password=os.getenv("ANON_PASSWORD"),
                first_name=fake.first_name(),
                last_name=fake.last_name(),
                is_email_verified=random.choice([True, False]),
                phone=generate_nigerian_phone_number(),
            )
            staff = Staff.objects.create(
                user=user,
                occupation=fake.job(),
                role=random.choice(["admin", "moderator", "volunteer"]),
            )
            staff.set_verification_override(random.choice([True, False]))
            staff_list.append(staff)

        # Create candidate users
        candidate_list = []
        for i in range(100):
            user = User.objects.create_user(
                email=f"candidate{i+1}@mail.com",
                password=os.getenv("ANON_PASSWORD"),
                first_name=fake.first_name(),
                last_name=fake.last_name(),
                is_email_verified=random.choice([True, False]),
                phone=generate_nigerian_phone_number(),
            )
            candidate = Candidate.objects.create(
                user=user,
                school=fake.company() + " High",
                role=random.choice(["league", "screening"]),
            )
            candidate.set_verification_override(random.choice([True, False]))
            candidate_list.append(candidate)

        # Create questions
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
                difficulty=random.choice(["easy", "medium", "hard"]),
            )
            question_list.append(question)

        # Create exams
        exam_list = []
        for i in range(10):
            exam = Exam.objects.create(
                stage=random.choice(["screening", "league"]),
                title=fake.catch_phrase(),
                description=fake.text(),
                created_by=random.choice(staff_list),
                is_active=True,
                exam_date=timezone.now() - timezone.timedelta(days=random.randint(1, 30)),
            )
            # Add a random number of questions to each exam
            exam.questions.set(random.sample(question_list, k=random.randint(5, 20)))
            exam_list.append(exam)

        # Create Candidate scores and answers
        for candidate in candidate_list:
            # Have each candidate take a random number of exams
            exams_to_take = random.sample(exam_list, k=random.randint(1, 5))
            for exam in exams_to_take:
                score = CandidateScore.objects.create(
                    candidate=candidate,
                    exam=exam,
                    score=round(random.uniform(30.0, 100.0), 2),
                    submitted_by=random.choice(staff_list),
                )
                # Create answers for each question in the exam
                for question in exam.questions.all():
                    CandidateAnswer.objects.create(
                        candidate_score=score,
                        question=question,
                        selected_option=random.choice(["A", "B", "C", "D"]),
                    )

        self.stdout.write(self.style.SUCCESS("Database populated successfully with more data!"))