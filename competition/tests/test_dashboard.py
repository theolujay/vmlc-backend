from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework_api_key.models import APIKey

from identity.models import User, Candidate
from competition.models import Competition, Stage, StageExam, Enrollment
from vmlc.models import Exam

class CandidateDashboardViewTest(APITestCase):
    def setUp(self):
        # Create API Key
        self.api_key_obj, self.api_key = APIKey.objects.create_key(name="test-key")
        self.client.credentials(HTTP_X_API_KEY=self.api_key)

        # Create user and candidate
        self.user = User.objects.create_user(
            email="candidate@example.com", 
            password="SecurePass123!",
            first_name="John",
            last_name="Doe",
            phone="+2348012345678",
            state="Lagos"
        )
        self.candidate = Candidate.objects.create(
            user=self.user,
            school_name="Test School",
            school_type="public",
            role=Candidate.Roles.SCREENING
        )
        
        # Authenticate
        self.client.force_authenticate(user=self.user)
        
        # Create active competition
        self.competition = Competition.objects.create(
            name="Test Comp",
            edition=1,
            status=Competition.Status.ACTIVE
        )
        
        # Create Screening Stage
        self.stage = Stage.objects.create(
            competition=self.competition,
            type=Stage.Type.SCREENING,
            order=1
        )
        
        # Enroll candidate
        self.enrollment = Enrollment.objects.create(
            candidate=self.candidate,
            competition=self.competition,
            current_stage=self.stage,
            status=Enrollment.Status.ACTIVE
        )
        
        # Create competition_slot
        self.stage_exam = StageExam.objects.create(
            competition_stage=self.stage,
            round=1,
            is_active=True
        )
        # Create Exam
        self.exam = Exam.objects.create(
            scheduled_date=timezone.now() + timezone.timedelta(days=1),
            open_duration_hours=12,
            competition_slot=self.stage_exam,
            is_active=True
        )
        

    def test_dashboard_flow(self):
        # 1. First call - should calculate data, return 200, and cache it
        url = reverse("competition:candidate-dashboard")
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.data
        
        # Verify structure
        self.assertIn("candidate_context", data)
        self.assertIn("enrollment_stage_progress", data)
        self.assertIn("active_exam", data)
        self.assertIn("performance_snapshot", data)
        self.assertIn("exam_history", data)
        
        # Verify Content
        self.assertEqual(data["candidate_context"]["full_name"], "John Doe")
        self.assertEqual(data["enrollment_stage_progress"]["current_stage"], "screening")
        self.assertEqual(data["active_exam"]["title"], "Screening")

        # 2. Second call - should return 200 from cache
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
