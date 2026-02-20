from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework_api_key.models import APIKey
from django.utils import timezone

from identity.models import User, Candidate
from competition.models import Competition, Stage, StageExam, Enrollment
from vmlc.models import Exam, CandidateExamResult
from vmlc.services.candidate_records import CandidateRecordService


class CandidateRecordServiceTest(APITestCase):
    def setUp(self):
        self.api_key, self.key = APIKey.objects.create_key(name="test-key")
        self.client.credentials(HTTP_X_API_KEY=self.key)
        # Setup candidate and competition
        self.user = User.objects.create_user(
            email="candidate_rec@example.com",
            password="password",
            first_name="Jane",
            last_name="Doe",
            phone="+2348022222222",
            state="Lagos",
        )
        self.candidate = Candidate.objects.create(
            user=self.user, school_name="Jane's School", role=Candidate.Roles.LEAGUE
        )

        self.competition = Competition.objects.create(
            name="VMLC 2026", edition=1, status=Competition.Status.ACTIVE
        )
        self.stage = Stage.objects.create(
            competition=self.competition, type=Stage.Type.LEAGUE, order=1
        )
        self.enrollment = Enrollment.objects.create(
            candidate=self.candidate,
            competition=self.competition,
            current_stage=self.stage,
            status=Enrollment.Status.ACTIVE,
        )

        # Create a stage exam slot
        self.stage_exam = StageExam.objects.create(
            competition_stage=self.stage, round=1, is_active=True
        )

        # Create an available exam linked to the slot
        self.exam = Exam.objects.create(
            competition_slot=self.stage_exam,
            scheduled_date=timezone.now() - timezone.timedelta(hours=1),
            open_duration_hours=12,
            is_active=True,
        )

    def test_get_available_exams(self):
        exams = CandidateRecordService.get_available_exams(self.candidate)
        self.assertEqual(len(exams), 1)
        self.assertEqual(exams[0]["round"], 1)



    def test_exam_history_view_failure(self):
        # Record a result
        CandidateExamResult.objects.create(
            candidate=self.candidate, exam=self.exam, score=85.0
        )

        self.client.force_authenticate(user=self.user)
        url = reverse(
            "vmlc:candidate-exam-history", kwargs={"candidate_id": self.candidate.pk}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        # self.assertEqual(len(response.data), 1)
        # self.assertEqual(response.data[0]["score"], 85.0)
