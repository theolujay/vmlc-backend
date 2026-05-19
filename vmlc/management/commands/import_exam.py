import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from competition.models import Competition, Stage, StageExam
from identity.models import Staff
from vmlc.models import Exam, Question


class Command(BaseCommand):
    help = "Import an exam and its questions from a JSON file."

    def add_arguments(self, parser):
        parser.add_argument(
            "file_path", type=str, help="Path to the JSON file to import"
        )
        parser.add_argument(
            "--staff-email",
            type=str,
            help="Email of the staff user to associate with created records",
        )
        parser.add_argument(
            "--competition-id",
            type=int,
            help="ID of the competition to link the exam to (if stage info is present)",
        )

    def handle(self, *args, **options):
        file_path = options["file_path"]
        staff_email = options.get("staff_email")
        competition_id = options.get("competition_id")
        if competition_id is None:
            competition = Competition.objects.filter(
                status=Competition.Status.ACTIVE
            ).first()
            if competition is None:
                raise CommandError(
                    "No active competition found. Provide --competition-id or create an active competition."
                )
            competition_id = competition.id

        try:
            with open(file_path, "r") as f:
                data = json.load(f)
        except Exception as e:
            raise CommandError(f"Failed to read file: {e}")

        staff = None
        if staff_email:
            try:
                staff = Staff.objects.get(user__email=staff_email)
            except Staff.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(f"Staff with email {staff_email} not found.")
                )

        if not staff:
            staff = Staff.objects.first()
            if not staff:
                self.stdout.write(
                    self.style.WARNING("No staff user found in the system.")
                )

        try:
            with transaction.atomic():
                questions = []
                for q_data in data.get("questions", []):
                    question, created = Question.objects.get_or_create(
                        text=q_data["text"],
                        option_a=q_data["option_a"],
                        option_b=q_data["option_b"],
                        option_c=q_data["option_c"],
                        option_d=q_data["option_d"],
                        correct_answer=q_data["correct_answer"],
                        defaults={
                            "difficulty": q_data.get("difficulty", "moderate"),
                            "image": q_data.get("image"),
                            "created_by": staff,
                        },
                    )
                    questions.append(question)

                from django.utils.dateparse import parse_datetime

                scheduled_date_raw = data.get("scheduled_date")
                scheduled_date = None
                if scheduled_date_raw:
                    scheduled_date = parse_datetime(scheduled_date_raw)

                exam = Exam.objects.create(
                    description=data.get("description"),
                    delivery_mode=data.get("delivery_mode", "online"),
                    scheduled_date=scheduled_date,
                    open_duration_hours=data.get("open_duration_hours"),
                    countdown_minutes=data.get("countdown_minutes"),
                    is_active=data.get("is_active", True),
                    created_by=staff,
                )
                exam.questions.set(questions)

                # Handle StageExam link if data is present and competition_id is provided
                stage_data = data.get("stage_exam")
                if stage_data and competition_id:
                    try:
                        competition = Competition.objects.get(id=competition_id)
                        stage = Stage.objects.get(
                            competition=competition, type=stage_data["stage_type"]
                        )
                        stage_exam, _ = StageExam.objects.get_or_create(
                            competition_stage=stage,
                            round=stage_data.get("round"),
                            defaults={
                                "config": stage_data.get("config", {}),
                            },
                        )
                        exam.competition_slot = stage_exam
                        exam.save()
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Linked exam to {stage.get_type_display()} stage."
                            )
                        )
                    except (Competition.DoesNotExist, Stage.DoesNotExist) as e:
                        self.stdout.write(
                            self.style.WARNING(
                                f"Could not link to stage: {e}. Skipping stage linking."
                            )
                        )

                self.stdout.write(
                    self.style.SUCCESS(f"Successfully imported exam with ID: {exam.id}")
                )

        except Exception as e:
            raise CommandError(f"Failed to import exam: {e}")
