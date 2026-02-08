from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from django.core.cache import cache
from comms.models import Notification
from rest_framework_api_key.models import APIKey

User = get_user_model()


class NotificationHTTPTest(APITestCase):

    def setUp(self):
        self.api_key, self.key = APIKey.objects.create_key(name="test-key")
        self.client.credentials(HTTP_X_API_KEY=self.key)
        self.user = User.objects.create_user(
            email="user@example.com",
            password="password123",
            first_name="Test",
            last_name="User",
        )
        self.client.force_authenticate(user=self.user)

        # Create some notifications
        self.n1 = Notification.objects.create(
            recipient=self.user, subject="N1", message="M1"
        )
        self.n2 = Notification.objects.create(
            recipient=self.user, subject="N2", message="M2"
        )

        # Clear cache for user
        cache.delete(f"notification_stats_{self.user.id}")
        cache.delete(f"notifications_version_{self.user.id}")

    def test_list_notifications(self):
        url = reverse("comms:notifications-history")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertEqual(response.data["stats"]["unread_count"], 2)

    def test_mark_as_read(self):
        url = reverse(
            "comms:mark-notification-as-read", kwargs={"notification_id": self.n1.id}
        )
        response = self.client.patch(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.n1.refresh_from_db()
        self.assertTrue(self.n1.is_read_by_recipient)

        # Verify cache invalidation (stats should be recalculated on next GET)
        url_list = reverse("comms:notifications-history")
        response_list = self.client.get(url_list)
        self.assertEqual(response_list.data["stats"]["unread_count"], 1)

    def test_mark_all_as_read(self):
        url = reverse("comms:mark-all-notifications-as-read")
        response = self.client.patch(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["updated_count"], 2)

        self.n1.refresh_from_db()
        self.n2.refresh_from_db()
        self.assertTrue(self.n1.is_read_by_recipient)
        self.assertTrue(self.n2.is_read_by_recipient)

        # Verify cache invalidation
        url_list = reverse("comms:notifications-history")
        response_list = self.client.get(url_list)
        self.assertEqual(response_list.data["stats"]["unread_count"], 0)

    def test_mark_as_read_not_found(self):
        url = reverse(
            "comms:mark-notification-as-read", kwargs={"notification_id": 9999}
        )
        response = self.client.patch(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
