from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from unittest.mock import patch, MagicMock, AsyncMock

from identity.models import Staff, Candidate
from comms.models import HelpdeskThread, ThreadMessage, MessageRead
from vmlc.models import Exam, ExamAccess

User = get_user_model()


class HelpdeskTests(APITestCase):

    def setUp(self):
        # Create Candidate
        self.candidate_user = User.objects.create_user(
            email="candidate@example.com",
            password="password123",
            first_name="Candidate",
            last_name="User",
        )
        self.candidate_profile = Candidate.objects.create(
            user=self.candidate_user, school_name="Test School"
        )

        # Create Staff
        self.staff_user = User.objects.create_user(
            email="staff@example.com",
            password="password123",
            first_name="Staff",
            last_name="User",
        )
        self.staff_profile = Staff.objects.create(
            user=self.staff_user, role=Staff.Roles.ADMIN
        )

        # Create another Staff
        # self.staff_user2 = User.objects.create_user(
        #     email="staff2@example.com",
        #     password="password123",
        #     first_name="Staff",
        #     last_name="User2",
        # )
        # self.staff_profile2 = Staff.objects.create(
        #     user=self.staff_user2,
        #     role=Staff.Roles.ADMIN
        # )

    def test_get_or_create_thread_candidate(self):
        """Test that a candidate can get or create their support thread."""
        self.client.force_authenticate(user=self.candidate_user)
        url = reverse("comms:helpdesk-thread")

        # First call creates the thread
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            HelpdeskThread.objects.filter(candidate=self.candidate_profile).exists()
        )

        # Verify system message
        thread = HelpdeskThread.objects.get(candidate=self.candidate_profile)
        self.assertEqual(thread.messages.count(), 1)
        self.assertEqual(
            thread.messages.first().sender_type, ThreadMessage.SenderType.SYSTEM
        )

    @patch("channels.layers.get_channel_layer")
    def test_post_message_candidate(self, mock_get_channel_layer):
        """Test candidate posting a message to their thread."""
        mock_layer = MagicMock()
        mock_layer.group_send = AsyncMock()
        mock_get_channel_layer.return_value = mock_layer

        self.client.force_authenticate(user=self.candidate_user)
        thread = HelpdeskThread.objects.create(candidate=self.candidate_profile)

        url = reverse("comms:helpdesk-thread-message", kwargs={"thread_id": thread.id})
        data = {"text": "Hello helpdesk!"}

        with patch(
            "comms.tasks.helpdesk_escalation_task.apply_async"
        ) as mock_escalation:
            response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            thread.messages.filter(
                sender_type=ThreadMessage.SenderType.CANDIDATE
            ).count(),
            1,
        )

        # Verify WebSocket broadcast
        mock_layer.group_send.assert_called()

        # Verify escalation task scheduled
        mock_escalation.assert_called_once()

    def test_staff_list_threads(self):
        """Test staff listing helpdesk threads."""
        HelpdeskThread.objects.create(candidate=self.candidate_profile)

        self.client.force_authenticate(user=self.staff_user)
        url = reverse("comms:staff-helpdesk-threads")

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

    def test_staff_detail_marks_read(self):
        """Test that staff opening a thread marks messages as read."""
        thread = HelpdeskThread.objects.create(candidate=self.candidate_profile)
        msg = ThreadMessage.objects.create(
            thread=thread,
            sender=self.candidate_user,
            sender_type=ThreadMessage.SenderType.CANDIDATE,
            text="Unread message",
        )

        self.client.force_authenticate(user=self.staff_user)
        url = reverse("comms:staff-helpdesk-thread-detail", kwargs={"id": thread.id})

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify message marked as read
        self.assertTrue(
            MessageRead.objects.filter(message=msg, user=self.staff_user).exists()
        )

    @patch("comms.tasks.slack_service.send_support_escalation_alert")
    @patch("comms.tasks.notification_service.notify_user")
    def test_escalation_task_triggers_on_no_reply(self, mock_notify, mock_slack):
        """Test that escalation task triggers notifications if no staff reply and candidate is in ongoing exam."""
        from comms.tasks import helpdesk_escalation_task

        # Create a real Exam and ExamAccess instance for the test
        exam = Exam.objects.create(
            description="Test Exam",
            scheduled_date=timezone.now()
            - timezone.timedelta(hours=1),  # Started an hour ago
            open_duration_hours=2,  # Open for 2 hours
        )
        # Use the override field
        exam._status_override = Exam.Status.ONGOING
        exam.save()

        ExamAccess.objects.create(
            candidate=self.candidate_profile,
            exam=exam,
            status=ExamAccess.Status.STARTED,
            deadline=timezone.now()
            + timezone.timedelta(minutes=10),  # Set a future deadline
        )

        thread = HelpdeskThread.objects.create(candidate=self.candidate_profile)
        msg = ThreadMessage.objects.create(
            thread=thread,
            sender=self.candidate_user,
            sender_type=ThreadMessage.SenderType.CANDIDATE,
            text="I need help with my exam!",
            metadata={"exam_id": str(exam.id)},  # Include exam_id in metadata
        )

        # Manually run the task
        helpdesk_escalation_task(msg.id)

        # Verify Slack and Email/SMS were triggered
        mock_slack.assert_called_once()
        self.assertTrue(mock_notify.called)

    @patch("comms.tasks.slack_service.send_support_escalation_alert")
    def test_escalation_task_does_not_trigger_if_no_ongoing_exam(self, mock_slack):
        """Test that escalation task does NOT trigger if no ongoing exam."""
        from comms.tasks import helpdesk_escalation_task

        # Create a real Exam and ExamAccess instance for the test, but make it not ongoing
        exam = Exam.objects.create(
            description="Test Exam",
            scheduled_date=timezone.now()
            - timezone.timedelta(hours=3),  # Concluded 3 hours ago
            open_duration_hours=1,  # Open for 1 hour
        )
        exam._status_override = Exam.Status.CONCLUDED  # Use the override field
        exam.save()  # Save the override

        ExamAccess.objects.create(
            candidate=self.candidate_profile,
            exam=exam,
            status=ExamAccess.Status.SUBMITTED,  # Not started
            deadline=timezone.now() - timezone.timedelta(minutes=10),  # Past deadline
        )

        thread = HelpdeskThread.objects.create(candidate=self.candidate_profile)
        msg = ThreadMessage.objects.create(
            thread=thread,
            sender=self.candidate_user,
            sender_type=ThreadMessage.SenderType.CANDIDATE,
            text="I need help, but not with an exam.",
            metadata={
                "exam_id": str(exam.id)
            },  # Still include exam_id but access will fail
        )

        # Run the task for the candidate message
        helpdesk_escalation_task(msg.id)

        # Verify Slack was NOT triggered
        mock_slack.assert_not_called()

    @patch("comms.tasks.slack_service.send_support_escalation_alert")
    def test_escalation_task_does_not_trigger_if_staff_replied(self, mock_slack):
        """Test that escalation task does NOT trigger if a staff has already replied."""
        from comms.tasks import helpdesk_escalation_task

        thread = HelpdeskThread.objects.create(candidate=self.candidate_profile)
        candidate_msg = ThreadMessage.objects.create(
            thread=thread,
            sender=self.candidate_user,
            sender_type=ThreadMessage.SenderType.CANDIDATE,
            text="I need help!",
        )

        # Staff replies
        ThreadMessage.objects.create(
            thread=thread,
            sender=self.staff_user,
            sender_type=ThreadMessage.SenderType.STAFF,
            text="I am here to help.",
        )

        # Run the task for the candidate message
        helpdesk_escalation_task(candidate_msg.id)

        # Verify Slack was NOT triggered
        mock_slack.assert_not_called()

    # def test_staff_list_threads_unread_count_any_staff_read(self):
    #     """
    #     Test that `unread_cnt` in StaffHelpdeskThreadListView is 0 if any staff has read the message.
    #     """
    #     # Create a helpdesk thread and a message from the candidate
    #     thread = HelpdeskThread.objects.create(candidate=self.candidate_profile)
    #     candidate_msg = ThreadMessage.objects.create(
    #         thread=thread,
    #         sender=self.candidate_user,
    #         sender_type=ThreadMessage.SenderType.CANDIDATE,
    #         text="Help me, please!"
    #     )

    #     # Staff user 1 reads the message
    #     self.client.force_authenticate(user=self.staff_user)
    #     detail_url = reverse("comms:staff-helpdesk-thread-detail", kwargs={"id": thread.id})
    #     self.client.get(detail_url) # This marks the message as read for staff_user

    #     # Now, staff user 2 lists the threads
    #     self.client.force_authenticate(user=self.staff_user2)
    #     list_url = reverse("comms:staff-helpdesk-threads")
    #     response = self.client.get(list_url)

    #     self.assertEqual(response.status_code, status.HTTP_200_OK)
    #     self.assertEqual(len(response.data['results']), 1)
    #     # Assert that the unread_cnt for the thread is 0, because staff_user has read it
    #     self.assertEqual(response.data['results'][0]['unread_cnt'], 0)
