import random
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from competition.models import Competition, Stage, StageExam, Enrollment
from vmlc.models import Exam, Question
from identity.models import Candidate, User, Staff


class Command(BaseCommand):
    help = "Sets up a demo competition environment."

    def add_arguments(self, parser):
        parser.add_argument(
            "--name",
            type=str,
            default="Demo Competition",
            help="Name of the competition",
        )
        parser.add_argument("--edition", type=int, default=1, help="Edition number")
        parser.add_argument(
            "--candidates",
            type=int,
            default=10,
            help="Number of demo candidates to create",
        )
        parser.add_argument(
            "--exam-id", type=str, help="UUID of an existing exam to use for Screening"
        )

    def handle(self, *args, **options):
        name = options["name"]
        edition = options["edition"]
        num_candidates = options["candidates"]
        exam_id = options.get("exam_id")

        with transaction.atomic():
            # 1. Create Competition
            competition, created = Competition.objects.get_or_create(
                name=name,
                edition=edition,
                defaults={
                    "status": Competition.Status.ACTIVE,
                    "start_date": timezone.now() + timedelta(days=1),
                    "end_date": timezone.now() + timedelta(days=30),
                },
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f"Created competition: {competition}")
                )
            else:
                self.stdout.write(f"Using existing competition: {competition}")

            # 2. Create Stages
            stages = {}
            for i, (s_type, s_label) in enumerate(Stage.Type.choices):
                stage, created = Stage.objects.get_or_create(
                    competition=competition,
                    type=s_type,
                    defaults={"order": i + 1, "description": f"Demo {s_label} stage"},
                )
                stages[s_type] = stage
                if created:
                    self.stdout.write(f"  Created stage: {s_label}")

            # 3. Get or Create a Demo Exam for Screening
            exam = None
            if exam_id:
                try:
                    exam = Exam.objects.get(id=exam_id)
                    self.stdout.write(f"Using provided exam: {exam}")
                except Exam.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Exam with ID {exam_id} not found. Creating a new one."
                        )
                    )

            if not exam:
                staff = Staff.objects.first()
                if not staff:
                    # Create a dummy staff if none exists
                    user, _ = User.objects.get_or_create(
                        username="demo_staff",
                        defaults={
                            "email": "staff@example.com",
                            "first_name": "Demo",
                            "last_name": "Staff",
                            "phone": "08012345678",
                            "state": "Lagos",
                        },
                    )
                    staff, _ = Staff.objects.get_or_create(
                        user=user,
                        defaults={
                            "occupation": "Coordinator",
                            "role": Staff.Roles.SUPERADMIN,
                        },
                    )
                exam, created = Exam.objects.get_or_create(
                    description=f"Demo Exam for {competition.name} Screening",
                    defaults={
                        "delivery_mode": Exam.ExamDeliveryMode.ONLINE,
                        "scheduled_date": timezone.now() + timedelta(minutes=2),
                        "open_duration_hours": 2,
                        "countdown_minutes": 60,
                        "created_by": staff,
                    },
                )
                if created:
                    self.stdout.write(self.style.SUCCESS(f"Created demo exam: {exam}"))
                else:
                    self.stdout.write(f"Using existing demo exam: {exam}")

            # Link exam to Screening stage
            stage_exam, _ = StageExam.objects.get_or_create(
                competition_stage=stages["screening"],
                defaults={"is_active": True},
            )
            exam.competition_slot = stage_exam
            exam.save()
            self.stdout.write(self.style.SUCCESS(f"Linked exam to Screening stage"))

            # 4. Create Demo Candidates and Enroll them
            for i in range(num_candidates):
                email = f"demo_candidate{i}.vmlc@mailsac.com"
                user, u_created = User.objects.get_or_create(
                    email=email,
                    defaults={
                        "username": email,
                        "first_name": "Demo",
                        "last_name": f"Candidate {i}",
                        "phone": f"07012345{i:03d}",
                        "state": "Lagos",
                        "is_email_verified": True,
                    },
                )
                if u_created:
                    user.set_password("password123")
                    user.save()

                candidate, c_created = Candidate.objects.get_or_create(
                    user=user,
                    defaults={
                        "school_name": "Demo Academy",
                        "school_type": "public",
                        "current_class": "SS3",
                    },
                )

                enrollment, e_created = Enrollment.objects.get_or_create(
                    candidate=candidate,
                    competition=competition,
                    defaults={"current_stage": stages["screening"]},
                )
                if e_created:
                    self.stdout.write(f"  Enrolled candidate: {email}")

            self.stdout.write(self.style.SUCCESS("Demo environment setup complete."))
