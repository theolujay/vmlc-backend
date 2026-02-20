import json
import os
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from io import StringIO

from vmlc.models import Exam, Question
from identity.models import Staff, User
from competition.models import Competition, Stage, StageExam

class ExamCommandsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="admin@example.com", password="password")
        self.staff = Staff.objects.create(user=self.user)

        self.competition = Competition.objects.create(name="Comp", edition=1, status=Competition.Status.ACTIVE)
        self.stage = Stage.objects.create(competition=self.competition, type=Stage.Type.SCREENING, order=1)
        self.slot = StageExam.objects.create(competition_stage=self.stage, round=None)

        self.question = Question.objects.create(
            text="Q1", option_a="A", option_b="B", option_c="C", option_d="D",
            correct_answer="A", created_by=self.staff
        )

        self.exam = Exam.objects.create(
            description="Export Test",
            scheduled_date=timezone.now(),
            open_duration_hours=1,
            countdown_minutes=30,
            created_by=self.staff,
            competition_slot=self.slot
        )
        self.exam.questions.add(self.question)

    def test_export_import_exam(self):
        # 1. Export
        out = StringIO()
        call_command('export_exam', str(self.exam.id), stdout=out)
        export_data = json.loads(out.getvalue())

        self.assertEqual(export_data['description'], "Export Test")
        self.assertEqual(len(export_data['questions']), 1)

        # Save to temp file
        temp_file = "/tmp/exam_export.json"
        with open(temp_file, 'w') as f:
            json.dump(export_data, f)

        # 2. Import into a NEW competition
        new_comp = Competition.objects.create(name="New Comp", edition=2)
        Stage.objects.create(competition=new_comp, type=Stage.Type.SCREENING, order=1)

        in_out = StringIO()
        call_command('import_exam', temp_file, staff_email=self.user.email, competition_id=new_comp.id, stdout=in_out)

        import_output = in_out.getvalue()
        self.assertIn("Successfully imported exam", import_output)

        # Verify imported exam
        new_exam = Exam.objects.exclude(id=self.exam.id).first()
        self.assertIsNotNone(new_exam)
        self.assertEqual(new_exam.description, "Export Test")
        self.assertEqual(new_exam.competition_slot.competition_stage.competition, new_comp)

        if os.path.exists(temp_file):
            os.remove(temp_file)
