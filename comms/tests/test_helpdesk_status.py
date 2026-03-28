from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta

from identity.models import Staff, Candidate
from comms.models import HelpdeskThread, ThreadMessage, MessageRead
from comms.tasks import cleanup_snoozed_helpdesk_threads_task

User = get_user_model()


class HelpdeskStatusTests(APITestCase):

    def setUp(self):
        cache.clear()
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

        self.thread = HelpdeskThread.objects.create(candidate=self.candidate_profile)

    def test_staff_update_status_to_closed(self):
        self.client.force_authenticate(user=self.staff_user)
        url = reverse(
            "comms:staff-helpdesk-thread-action", kwargs={"id": self.thread.id}
        )
        data = {"status": HelpdeskThread.Status.CLOSED}
        response = self.client.patch(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.thread.refresh_from_db()
        self.assertEqual(self.thread.status, HelpdeskThread.Status.CLOSED)

    def test_staff_update_status_to_snoozed(self):
        self.client.force_authenticate(user=self.staff_user)
        url = reverse(
            "comms:staff-helpdesk-thread-action", kwargs={"id": self.thread.id}
        )
        snoozed_until = timezone.now() + timedelta(days=1)
        data = {
            "status": HelpdeskThread.Status.SNOOZED,
            "snoozed_until": snoozed_until.isoformat(),
        }
        response = self.client.patch(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.thread.refresh_from_db()
        self.assertEqual(self.thread.status, HelpdeskThread.Status.SNOOZED)
        self.assertIsNotNone(self.thread.snoozed_until)

    def test_staff_update_to_snoozed_requires_until(self):
        self.client.force_authenticate(user=self.staff_user)
        url = reverse(
            "comms:staff-helpdesk-thread-action", kwargs={"id": self.thread.id}
        )
        data = {"status": HelpdeskThread.Status.SNOOZED}
        response = self.client.patch(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("snoozed_until", response.data)

    def test_candidate_message_sets_open(self):
        self.thread.status = HelpdeskThread.Status.CLOSED
        self.thread.save()

        self.client.force_authenticate(user=self.candidate_user)
        url = reverse(
            "comms:helpdesk-thread-message", kwargs={"thread_id": self.thread.id}
        )
        data = {"text": "New message"}
        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.thread.refresh_from_db()
        self.assertEqual(self.thread.status, HelpdeskThread.Status.OPEN)

    def test_candidate_message_respects_active_snooze(self):
        snoozed_until = timezone.now() + timedelta(days=1)
        self.thread.status = HelpdeskThread.Status.SNOOZED
        self.thread.snoozed_until = snoozed_until
        self.thread.save()

        self.client.force_authenticate(user=self.candidate_user)
        url = reverse(
            "comms:helpdesk-thread-message", kwargs={"thread_id": self.thread.id}
        )
        data = {"text": "New message during snooze"}
        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.thread.refresh_from_db()
        self.assertEqual(self.thread.status, HelpdeskThread.Status.SNOOZED)

    def test_candidate_message_reverts_expired_snooze(self):
        snoozed_until = timezone.now() - timedelta(days=1)
        self.thread.status = HelpdeskThread.Status.SNOOZED
        self.thread.snoozed_until = snoozed_until
        self.thread.save()

        self.client.force_authenticate(user=self.candidate_user)
        url = reverse(
            "comms:helpdesk-thread-message", kwargs={"thread_id": self.thread.id}
        )
        data = {"text": "New message after snooze expired"}
        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.thread.refresh_from_db()
        self.assertEqual(self.thread.status, HelpdeskThread.Status.OPEN)
        self.assertIsNone(self.thread.snoozed_until)

    def test_staff_message_sets_in_progress(self):
        self.thread.status = HelpdeskThread.Status.OPEN
        self.thread.save()

        self.client.force_authenticate(user=self.staff_user)
        url = reverse(
            "comms:helpdesk-thread-message", kwargs={"thread_id": self.thread.id}
        )
        data = {"text": "Staff reply"}
        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.thread.refresh_from_db()
        self.assertEqual(self.thread.status, HelpdeskThread.Status.IN_PROGRESS)

    def test_candidate_reads_messages_sets_in_progress(self):
        self.thread.status = HelpdeskThread.Status.OPEN
        self.thread.save()

        # Staff sent a message
        ThreadMessage.objects.create(
            thread=self.thread,
            sender=self.staff_user,
            sender_type=ThreadMessage.SenderType.STAFF,
            text="Staff message",
        )

        self.client.force_authenticate(user=self.candidate_user)
        url = reverse("comms:helpdesk-thread")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.thread.refresh_from_db()
        self.assertEqual(self.thread.status, HelpdeskThread.Status.IN_PROGRESS)

    def test_cleanup_task_reverts_expired_snooze(self):
        snoozed_until = timezone.now() - timedelta(days=1)
        self.thread.status = HelpdeskThread.Status.SNOOZED
        self.thread.snoozed_until = snoozed_until
        self.thread.save()

        cleanup_snoozed_helpdesk_threads_task()

        self.thread.refresh_from_db()
        self.assertEqual(self.thread.status, HelpdeskThread.Status.OPEN)
        self.assertIsNone(self.thread.snoozed_until)

    def test_staff_list_filters_closed_and_snoozed_by_default(self):
        # Create a message so thread is eligible for list
        ThreadMessage.objects.create(
            thread=self.thread,
            sender=self.candidate_user,
            sender_type=ThreadMessage.SenderType.CANDIDATE,
            text="Need help",
        )

        self.client.force_authenticate(user=self.staff_user)
        url = reverse("comms:staff-helpdesk-threads")

        # 1. OPEN status (default) - should be in list
        self.thread.status = HelpdeskThread.Status.OPEN
        self.thread.save()
        response = self.client.get(url)
        self.assertEqual(len(response.data["results"]), 1)

        # 2. CLOSED status - should NOT be in list
        self.thread.status = HelpdeskThread.Status.CLOSED
        self.thread.save()
        cache.clear()  # Clear version-based cache
        response = self.client.get(url)
        self.assertEqual(len(response.data["results"]), 0)

        # 3. SNOOZED status - should NOT be in list
        self.thread.status = HelpdeskThread.Status.SNOOZED
        self.thread.snoozed_until = timezone.now() + timedelta(days=1)
        self.thread.save()
        cache.clear()
        response = self.client.get(url)
        self.assertEqual(len(response.data["results"]), 0)

        # 4. Explicit status filter for SNOOZED - should be in list
        response = self.client.get(url + "?status=snoozed")
        self.assertEqual(len(response.data["results"]), 1)
