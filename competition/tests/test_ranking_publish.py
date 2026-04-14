from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework import status
from unittest.mock import patch, MagicMock
from django.utils.dateparse import parse_datetime

from identity.models import User, Candidate, Staff
from competition.models import (
    Competition,
    Stage,
    StageExam,
    RankingSnapshot,
    RankingSnapshotEntry,
)
from vmlc.models import Exam
from competition.tasks import (
    generate_ranking_and_update_leaderboard_task,
    update_leaderboard_task,
    invalidate_published_ranking_cache_task,
    publish_ranking_task,
)


class PublishRankingSnapshotViewTest(APITestCase):
    def setUp(self):
        # Create staff user
        self.staff_user = User.objects.create_user(
            email="staff@example.com", password="SecurePass123!", is_staff=True
        )
        self.staff_profile = Staff.objects.create(
            user=self.staff_user, role=Staff.Roles.SUPERADMIN
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
            is_published=False,
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
        data = {"exam_id": str(self.exam.id), "publish_now": True}

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
        data = {"exam_id": str(self.exam.id), "publish_now": True}

        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["error"], "No active ranking snapshot available to publish."
        )

    @patch("competition.tasks.publish_ranking_task.apply_async")
    def test_schedule_ranking_publication(self, mock_apply_async):
        """
        Test that scheduling a ranking publication works.
        """
        url = reverse("competition:publish-ranking-snapshot")
        publish_at = timezone.now() + timezone.timedelta(hours=1)
        data = {
            "exam_id": str(self.exam.id),
            "publish_at": publish_at.isoformat(),
        }

        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertIn("will go live", response.data["message"])

        # Verify ranking meta is updated
        self.ranking.refresh_from_db()
        # Compare as datetimes to avoid timezone string mismatch
        stored_publish_at = parse_datetime(self.ranking.meta["scheduled_publish_at"])
        self.assertEqual(stored_publish_at, publish_at)
        self.assertEqual(self.ranking.meta["scheduled_by"], str(self.staff_profile.pk))

        # Verify task was scheduled with ETA
        mock_apply_async.assert_called_once()
        args, kwargs = mock_apply_async.call_args
        self.assertEqual(kwargs["kwargs"]["ranking_snapshot_id"], self.ranking.id)
        self.assertEqual(kwargs["kwargs"]["actor_id"], self.staff_profile.pk)
        self.assertEqual(kwargs["eta"], publish_at)


class PublishRankingTaskTest(APITestCase):
    def setUp(self):
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
            is_published=False,
            meta={"scheduled_publish_at": "some_time"},
        )

    @patch("competition.tasks.invalidate_published_ranking_cache_task.delay")
    @patch("django.db.transaction.on_commit")
    def test_publish_ranking_task_success(self, mock_on_commit, mock_task_delay):
        """
        Test that publish_ranking_task works.
        """
        # Mock on_commit to execute the callback immediately
        mock_on_commit.side_effect = lambda func: func()

        publish_ranking_task(self.ranking.id)

        self.ranking.refresh_from_db()
        self.assertTrue(self.ranking.is_published)
        self.assertIsNotNone(self.ranking.published_at)
        self.assertNotIn("scheduled_publish_at", self.ranking.meta)

        # Verify invalidation task was called
        mock_task_delay.assert_called_once_with(ranking_snapshot_id=self.ranking.id)
