from django.urls import reverse
from django.utils import timezone
from django.core.cache import cache
from rest_framework.test import APITestCase
from rest_framework import status
from django.test import override_settings

from identity.models import User, Candidate, Staff
from competition.models import Competition, Stage, StageExam, CandidateCompetition, Standings, StandingsEntry
from vmlc.models import Exam, CandidateExamResult
from competition.tasks import cache_candidate_dashboard_task

class CandidateDashboardViewTest(APITestCase):
    def setUp(self):
        # Create user and candidate
        self.user = User.objects.create_user(
            email="candidate@example.com", 
            password="password",
            first_name="John",
            last_name="Doe",
            phone="+2348012345678",
            state="Lagos"
        )
        self.candidate = Candidate.objects.create(
            user=self.user,
            school_name="Test School",
            role=Candidate.Roles.LEAGUE
        )
        
        # Authenticate
        self.client.force_authenticate(user=self.user)
        
        # Create active competition
        self.competition = Competition.objects.create(
            name="Test Comp",
            edition=1,
            status=Competition.Status.ACTIVE
        )
        
        # Create League Stage
        self.stage = Stage.objects.create(
            competition=self.competition,
            type=Stage.Type.LEAGUE,
            order=1
        )
        
        # Enroll candidate
        self.participation = CandidateCompetition.objects.create(
            candidate=self.candidate,
            competition=self.competition,
            current_stage=self.stage,
            status=CandidateCompetition.Status.ACTIVE
        )
        
        # Create Exam
        self.exam = Exam.objects.create(
            title="League Round 1",
            scheduled_date=timezone.now() + timezone.timedelta(days=1),
            open_duration_hours=12,
            is_active=True
        )
        
        # Link Exam to Stage
        self.stage_exam = StageExam.objects.create(
            competition_stage=self.stage,
            round=1,
            exam=self.exam,
            is_active=True
        )

    def test_dashboard_flow(self):
        # 1. First call - should calculate data, return 200, and cache it
        url = reverse("vmlc:candidate-dashboard")
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.data
        
        # Verify structure
        self.assertIn("candidate_context", data)
        self.assertIn("stage_progress", data)
        self.assertIn("active_exam", data)
        self.assertIn("performance_snapshot", data)
        self.assertIn("exam_history", data)
        
        # Verify Content
        self.assertEqual(data["candidate_context"]["full_name"], "John Doe")
        self.assertEqual(data["stage_progress"]["current_stage"], "league")
        self.assertEqual(data["active_exam"]["title"], "League Round 1")

        # 2. Second call - should return 200 from cache
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
