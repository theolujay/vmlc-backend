from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITransactionTestCase
from django.contrib.auth import get_user_model
from rest_framework_api_key.models import APIKey
from django.utils import timezone
from unittest.mock import patch

from identity.models import Staff, UserVerification, Candidate
from comms.models import Broadcast, BroadcastLog

User = get_user_model()


class BroadcastTest(APITransactionTestCase):

    def setUp(self):
        self.api_key, self.key = APIKey.objects.create_key(name="test-key")
        self.client.credentials(HTTP_X_API_KEY=self.key)

        # Staff User
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

        # Candidate User
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

        self.client.force_authenticate(user=self.staff_user)

    def test_create_broadcast_basic(self):
        url = reverse("comms:broadcast-list-create")
        data = {
            "subject": "Test Subject",
            "message": "Test message...",
            "mediums": ["platform", "email"],
            "target_roles": {"candidate": ["league"]},
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Broadcast.objects.count(), 1)
        broadcast = Broadcast.objects.first()
        self.assertEqual(broadcast.subject, "Test Subject")

    def test_create_broadcast_with_sms(self):
        url = reverse("comms:broadcast-list-create")
        data = {
            "subject": "SMS Subject",
            "message": "SMS message content",
            "mediums": ["sms"],
            "target_roles": {"candidate": ["league"]},
        }
        with patch("comms.tasks.send_broadcast_task.apply_async") as mock_task:
            # Mock return value to have an 'id' attribute that is a string
            mock_task.return_value.id = "test-task-id"

            response = self.client.post(url, data, format="json")
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            mock_task.assert_called_once()

        broadcast = Broadcast.objects.get(subject="SMS Subject")
        self.assertIn("sms", broadcast.mediums)
        self.assertEqual(broadcast.task_id, "test-task-id")

    def test_list_broadcasts(self):
        Broadcast.objects.create(
            subject="B1",
            message="M1",
            mediums=["email"],
            target_roles={"staff": ["manager"]},
            created_by=self.staff_profile,
        )
        url = reverse("comms:broadcast-list-create")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertIn("broadcast_summary_data", response.data)

    def test_broadcast_detail(self):
        broadcast = Broadcast.objects.create(
            subject="Detail Test",
            message="Content",
            mediums=["platform"],
            target_roles={"candidate": ["league"]},
            created_by=self.staff_profile,
        )
        url = reverse("comms:broadcast-detail", kwargs={"broadcast_id": broadcast.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["subject"], "Detail Test")

    @patch("comms.services.notification.NotificationService.send_bulk_phone_msg")
    def test_broadcast_execution_sms(self, mock_send_bulk):
        from comms.services.notification import NotificationService

        broadcast = Broadcast.objects.create(
            subject="Execution Test",
            message="SMS Content",
            mediums=["sms"],
            target_roles={"candidate": ["league"]},
            created_by=self.staff_profile,
        )

        service = NotificationService()
        result = service.send_broadcast(broadcast.id)

        # Should be IN_PROGRESS because SMS log is PENDING (async)
        self.assertEqual(result["status"], Broadcast.Status.IN_PROGRESS)
        mock_send_bulk.assert_called_once()

        # Check logs
        log = BroadcastLog.objects.filter(broadcast=broadcast, medium="sms").first()
        self.assertIsNotNone(log)
        self.assertEqual(log.recipient_count, 1)
        self.assertEqual(log.status, BroadcastLog.MediumStatus.PENDING)

    def test_broadcast_validation_invalid_roles(self):
        url = reverse("comms:broadcast-list-create")
        data = {
            "subject": "Invalid Roles",
            "message": "Content",
            "mediums": ["email"],
            "target_roles": {"candidate": ["invalid_role"]},
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("target_roles", response.data)
