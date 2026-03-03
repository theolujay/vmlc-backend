from django.test import TestCase
from unittest.mock import patch, MagicMock
from django.utils import timezone
from datetime import timedelta
from identity.models import User, Candidate, Staff, UserVerification
from competition.models import (
    Competition,
    Stage,
    StageExam,
    Enrollment,
    EnrollmentStageProgress,
)
from vmlc.models import Exam
from comms.services.notification import NotificationService
from comms.models import Broadcast


class ExamNotificationTest(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            email="staff@example.com",
            password="password123",
            first_name="Staff",
            last_name="User",
        )
        self.staff_profile = Staff.objects.create(
            user=self.staff_user, role=Staff.Roles.MANAGER
        )
        UserVerification.objects.create(user=self.staff_user, is_approved=True)

        self.candidate_user = User.objects.create_user(
            email="candidate@example.com",
            password="password123",
            first_name="Candidate",
            last_name="One",
            phone="+2348012345678",
        )
        self.candidate_profile = Candidate.objects.create(
            user=self.candidate_user, role=Candidate.Roles.LEAGUE
        )
        UserVerification.objects.create(user=self.candidate_user, is_approved=True)

        self.competition = Competition.objects.create(
            name="Test Competition", edition=1
        )
        self.stage = Stage.objects.create(
            competition=self.competition, type=Stage.Type.LEAGUE, order=1
        )
        self.stage_exam = StageExam.objects.create(
            competition_stage=self.stage, round=1
        )
        self.exam = Exam.objects.create(
            id="00000000-0000-0000-0000-000000000001",
            competition_slot=self.stage_exam,
            scheduled_date=timezone.now() + timedelta(hours=1),
            open_duration_hours=2,
            is_active=True,
        )
        self.enrollment = Enrollment.objects.create(
            candidate=self.candidate_profile,
            competition=self.competition,
            current_stage=self.stage,
            status=Enrollment.Status.ACTIVE,
        )
        # We don't necessarily need EnrollmentStageProgress to be IN_PROGRESS now
        self.esp = EnrollmentStageProgress.objects.create(
            enrollment=self.enrollment,
            stage=self.stage,
            status=EnrollmentStageProgress.Status.PENDING,
        )

    @patch("comms.tasks.send_mail_task.delay")
    @patch("comms.services.notification.NotificationService.send_bulk_phone_msg")
    def test_notify_candidates_about_exam_calls_notify_user(
        self, mock_send_bulk, mock_send_mail
    ):
        service = NotificationService()

        # Avoid real DB/Group calls for platform notification
        with patch.object(
            NotificationService, "_send_platform_notification", return_value=True
        ):
            service.notify_candidates_about_exam(self.exam, "started")

        # Check if email task was queued
        mock_send_mail.assert_called()
        email_kwargs = mock_send_mail.call_args.kwargs
        self.assertIn("started", email_kwargs["subject"].lower())
        self.assertEqual(email_kwargs["recipient_list"], [self.candidate_user.email])
        self.assertIsNotNone(email_kwargs.get("html_message"))

        # Check if bulk SMS was queued
        mock_send_bulk.assert_called()
        sms_kwargs = mock_send_bulk.call_args.kwargs
        self.assertIn("started", sms_kwargs["body"].lower())
        self.assertEqual(sms_kwargs["medium"], "sms")
        self.assertIn("2348012345678", sms_kwargs["recipients"])
