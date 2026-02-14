import json
from django.core.management.base import BaseCommand, CommandError
from vmlc.models import Exam
from django.core.serializers.json import DjangoJSONEncoder


class Command(BaseCommand):
    help = "Export an exam and its questions to a JSON file."

    def add_arguments(self, parser):
        parser.add_argument("exam_id", type=str, help="UUID of the exam to export")
        parser.add_argument(
            "--output", "-o", type=str, help="Output file path (default: stdout)"
        )

    def handle(self, *args, **options):
        exam_id = options["exam_id"]
        try:
            exam = Exam.objects.get(id=exam_id)
        except Exam.DoesNotExist:
            raise CommandError(f"Exam with ID {exam_id} does not exist.")
        except Exception as e:
            raise CommandError(f"Invalid UUID: {exam_id}")

        questions_data = []
        for question in exam.questions.all():
            questions_data.append(
                {
                    "text": question.text,
                    "image": question.image.name if question.image else None,
                    "option_a": question.option_a,
                    "option_b": question.option_b,
                    "option_c": question.option_c,
                    "option_d": question.option_d,
                    "correct_answer": question.correct_answer,
                    "difficulty": question.difficulty,
                }
            )

        exam_data = {
            "description": exam.description,
            "delivery_mode": exam.delivery_mode,
            "scheduled_date": exam.scheduled_date,
            "open_duration_hours": exam.open_duration_hours,
            "countdown_minutes": exam.countdown_minutes,
            "is_active": exam.is_active,
            "questions": questions_data,
        }

        # Include StageExam info if it exists
        if exam.competition_slot:
            exam_data["stage_exam"] = {
                "round": exam.competition_slot.round,
                "config": exam.competition_slot.config,
                "stage_type": exam.competition_slot.competition_stage.type,
            }

        json_data = json.dumps(exam_data, cls=DjangoJSONEncoder, indent=4)

        output_path = options.get("output")
        if output_path:
            with open(output_path, "w") as f:
                f.write(json_data)
            self.stdout.write(
                self.style.SUCCESS(f"Successfully exported exam to {output_path}")
            )
        else:
            self.stdout.write(json_data)
