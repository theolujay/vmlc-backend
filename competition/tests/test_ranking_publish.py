from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework import status
from unittest.mock import patch, MagicMock

from identity.models import User, Candidate, Staff
from competition.models import Competition, Stage, StageExam, RankingSnapshot, RankingSnapshotEntry
from vmlc.models import Exam


class PublishRankingSnapshotViewTest(APITestCase):
    def setUp(self):
        # Create staff user
        self.staff_user = User.objects.create_user(
            email="staff@example.com",
            password="SecurePass123!",
            is_staff=True
        )
        self.staff_profile = Staff.objects.create(
            user=self.staff_user,
            role=Staff.Roles.ADMIN
        )

        # Authenticate
        self.client.force_authenticate(user=self.staff_user)

        # Create active competition
        self.competition = Competition.objects.create(
            name="Test Comp", edition=1, status=Competition.Status.ACTIVE
        )

        # Create Screening Stage
        self.stage = Stage.objects.create(
            competition=self.competition, type=Stage.Type.SCREENING, order=1
        )

        # Create competition_slot
        self.stage_exam = StageExam.objects.create(
            competition_stage=self.stage, round=1, is_active=True
        )
        # Create Exam
        self.exam = Exam.objects.create(
            scheduled_date=timezone.now() - timezone.timedelta(days=1),
            open_duration_hours=12,
            competition_slot=self.stage_exam,
            is_active=True,
        )

        # Create an active RankingSnapshot for this exam
        self.ranking = RankingSnapshot.objects.create(
            competition=self.competition,
            stage=self.stage.type,
            round=1,
            exam=self.exam,
            is_active=True,
            is_published=False
        )

    @patch("competition.tasks.invalidate_published_ranking_cache_task.delay")
    @patch("django.db.transaction.on_commit")
    def test_publish_ranking_snapshot_success(self, mock_on_commit, mock_task_delay):
        """
        Test that publishing a ranking snapshot works and triggers cache invalidation.
        """
        # Mock on_commit to execute the callback immediately
        mock_on_commit.side_effect = lambda func: func()

        url = reverse("competition:publish-ranking-snapshot")
        data = {
            "exam_id": str(self.exam.id),
            "publish_now": True
        }

        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        # Verify ranking is published
        self.ranking.refresh_from_db()
        self.assertTrue(self.ranking.is_published)
        self.assertIsNotNone(self.ranking.published_at)

        # Verify invalidation task was called (via our immediate on_commit mock)
        mock_task_delay.assert_called_once_with(ranking_snapshot_id=self.ranking.id)

    def test_publish_ranking_snapshot_no_active_ranking(self):
        """
        Test that it returns 400 if no active ranking exists for the exam.
        """
        # Deactivate the ranking
        self.ranking.is_active = False
        self.ranking.save()

        url = reverse("competition:publish-ranking-snapshot")
        data = {
            "exam_id": str(self.exam.id),
            "publish_now": True
        }

        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"], "No active ranking snapshot available to publish.")
