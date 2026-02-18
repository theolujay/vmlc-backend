from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from comms.models import PublicSupportRequest


class SupportUsViewTests(APITestCase):
    def setUp(self):
        self.url = reverse("comms:support-us-inquiry")
        # _, self.api_key = APIKey.objects.create_key(name="test-key")
        self.valid_payload = {
            "full_name": "Test User",
            "email": "test@example.com",
            "type": "sponsorship",
            "message": "I want to sponsor.",
            "consent": True,
            "organization": "Test Org",
            "phone": "08012345678",
        }

    def test_submit_support_inquiry_success(self):
        """Test successful support inquiry submission."""
        with patch("comms.tasks.send_system_email_task") as mock_send_email:
            response = self.client.post(
                self.url,
                self.valid_payload,
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertEqual(PublicSupportRequest.objects.count(), 1)
            # Should call send_system_email twice (confirmation + notification)
            self.assertEqual(mock_send_email.delay.call_count, 2)

    def test_submit_support_inquiry_missing_fields(self):
        """Test submission with missing required fields."""
        payload = self.valid_payload.copy()
        del payload["full_name"]
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("full_name", response.data)

    def test_submit_support_inquiry_invalid_email(self):
        """Test submission with invalid email."""
        payload = self.valid_payload.copy()
        payload["email"] = "invalid-email"
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_submit_support_inquiry_no_consent(self):
        """Test submission without consent."""
        payload = self.valid_payload.copy()
        payload["consent"] = False
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("consent", response.data)
