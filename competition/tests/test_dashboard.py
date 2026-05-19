from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_api_key.models import APIKey

from competition.models import Competition, Enrollment, Stage, StageExam
from identity.models import Candidate, Staff, User
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
            state="Lagos",
        )
        self.candidate = Candidate.objects.create(
            user=self.user,
            school_name="Test School",
            school_type="public",
            role=Candidate.Roles.SCREENING,
        )

        # Authenticate
        self.client.force_authenticate(user=self.user)

        # Create active competition
        self.competition = Competition.objects.create(
            name="Test Comp", edition=1, status=Competition.Status.ACTIVE
        )

        # Create Screening Stage
        self.stage = Stage.objects.create(
            competition=self.competition, type=Stage.Type.SCREENING, order=1
        )

        # Enroll candidate
        self.enrollment = Enrollment.objects.create(
            candidate=self.candidate,
            competition=self.competition,
            current_stage=self.stage,
            status=Enrollment.Status.ACTIVE,
        )

        # Create competition_slot
        self.stage_exam = StageExam.objects.create(
            competition_stage=self.stage, round=1, is_active=True
        )
        # Create Exam
        self.exam = Exam.objects.create(
            scheduled_date=timezone.now() + timezone.timedelta(days=1),
            open_duration_hours=12,
            competition_slot=self.stage_exam,
            is_active=True,
        )

    def test_dashboard_flow(self):
        # 1. First call - should calculate data, return 200, and cache it
        url = reverse("competition:candidate-dashboard")

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.data

        # Verify structure
        # self.assertIn("candidate_context", data)
        self.assertIn("enrollment_stage_progress", data)
        self.assertIn("active_exam", data)
        self.assertIn("performance", data)
        self.assertIn("exam_history", data)

        # Verify Content
        # self.assertEqual(data["candidate_context"]["full_name"], "John Doe")
        self.assertEqual(
            data["enrollment_stage_progress"]["current_stage"], "screening"
        )
        self.assertEqual(data["active_exam"]["title"], "Screening")

        # Verify performance context
        performance = data["performance"]
        self.assertIn("active_context", performance)
        self.assertIn("history", performance)

        active_context = performance["active_context"]
        self.assertEqual(active_context["stage"], "screening")
        self.assertEqual(active_context["stage_display"], "Screening Stage")
        self.assertIn("status_meta", active_context)
        status_meta = active_context["status_meta"]
        self.assertEqual(status_meta["status_type"], "info")
        self.assertEqual(status_meta["has_taken_exam"], False)
        self.assertEqual(status_meta["color"], "#3E4095")
        self.assertEqual(status_meta["icon"], "info")

        # 2. Second call - should return 200 from cache
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class StaffCompetitionDashboardViewTest(APITestCase):
    def setUp(self):
        # Create API Key
        self.api_key_obj, self.api_key = APIKey.objects.create_key(name="test-key")
        self.client.credentials(HTTP_X_API_KEY=self.api_key)

        # Create staff user
        self.staff_user = User.objects.create_user(
            email="staff@example.com",
            password="SecurePass123!",
            first_name="Staff",
            last_name="User",
            phone="+2348011111111",
            state="Lagos",
        )
        self.staff_profile = Staff.objects.create(
            user=self.staff_user, occupation="Admin", role=Staff.Roles.ADMIN
        )

        # Authenticate as staff
        self.client.force_authenticate(user=self.staff_user)

        # Create active competition
        self.competition = Competition.objects.create(
            name="Test Staff Comp", edition=2, status=Competition.Status.ACTIVE
        )

        # Create Screening Stage
        self.screening_stage = Stage.objects.create(
            competition=self.competition, type=Stage.Type.SCREENING, order=1
        )

        # Create League Stage
        self.league_stage = Stage.objects.create(
            competition=self.competition, type=Stage.Type.LEAGUE, order=2
        )

        # Create a StageExam slot
        self.stage_exam_screening = StageExam.objects.create(
            competition_stage=self.screening_stage, round=1, is_active=True
        )

        # Create an Exam
        self.exam_screening = Exam.objects.create(
            scheduled_date=timezone.now() + timezone.timedelta(days=1),
            open_duration_hours=12,
            competition_slot=self.stage_exam_screening,
            is_active=True,
        )

        # Create another StageExam slot for League
        self.stage_exam_league = StageExam.objects.create(
            competition_stage=self.league_stage, round=1, is_active=True
        )

        # Create another Exam for League
        self.exam_league = Exam.objects.create(
            scheduled_date=timezone.now() + timezone.timedelta(days=7),  # Future date
            open_duration_hours=12,
            competition_slot=self.stage_exam_league,
            is_active=True,
        )

    def test_staff_dashboard_retrieval(self):
        url = reverse("competition:staff-competition-dashboard")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.data

        # Verify top-level structure
        self.assertIn("stats", data)
        self.assertIn("progress", data)
        self.assertIn("exams", data)
        self.assertIn("leaderboard_summary", data)
        self.assertIn("latest_ranking_summary", data)

        # Verify content of 'exams' list
        self.assertTrue(len(data["exams"]) > 0)
        first_exam = data["exams"][0]
        self.assertIn("id", first_exam)
        self.assertIn("title", first_exam)
        self.assertIn("stage", first_exam)
        self.assertIn("status", first_exam)
        self.assertIn("ranking_status", first_exam)  # Key that caused KeyError
        self.assertIn("stats", first_exam)

        self.assertEqual(first_exam["id"], str(self.exam_screening.id))
        self.assertEqual(
            first_exam["ranking_status"], "pending"
        )  # No snapshot created yet
