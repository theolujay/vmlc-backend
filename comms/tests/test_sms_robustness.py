from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from comms.models import Broadcast
from comms.services.notification import NotificationService

User = get_user_model()


class SMSRobustnessTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="testuser@example.com",
            password="password123",
            first_name="Test",
            last_name="User",
            phone="+2348012345678",
        )
        self.service = NotificationService()

    @patch("comms.tasks.send_bulk_sms_task.delay")
    @patch("django.conf.settings.SMS_PROVIDER", "kudi")
    def test_notify_user_sms_queues_task(self, mock_sms_task):
        """
        Verify that notify_user with medium='sms' enqueues send_bulk_sms_task
        when Kudi is the provider.
        """
        results = self.service.notify_user(
            user=self.user,
            subject="Test Subject",
            message="Test Message",
            mediums=[Broadcast.Medium.SMS],
        )

        # Check results map
        self.assertTrue(results.get("sms"))

        # Verify task was queued
        mock_sms_task.assert_called_once()
        args, kwargs = mock_sms_task.call_args
        self.assertIn("Test Subject: Test Message", kwargs["body"])
        self.assertEqual(kwargs["recipients"], ["2348012345678"])

    @patch("comms.services.notification.NotificationService.send_phone_msg")
    @patch("django.conf.settings.SMS_PROVIDER", "other")
    def test_notify_user_sms_direct_send_for_other_providers(self, mock_send_phone_msg):
        """
        Verify that notify_user with medium='sms' calls send_phone_msg directly
        when provider is NOT Kudi.
        """
        mock_send_phone_msg.return_value = {"success": True}

        results = self.service.notify_user(
            user=self.user,
            subject="Test Subject",
            message="Test Message",
            mediums=[Broadcast.Medium.SMS],
        )

        self.assertTrue(results.get("sms"))
        mock_send_phone_msg.assert_called_once()

    def test_notify_user_sms_no_phone(self):
        """
        Verify that notify_user returns False for SMS if user has no phone number.
        """
        self.user.phone = ""
        self.user.save()

        results = self.service.notify_user(
            user=self.user,
            subject="Test Subject",
            message="Test Message",
            mediums=[Broadcast.Medium.SMS],
        )

        self.assertFalse(results.get("sms"))

    @patch("comms.services.notification.TwilioClient")
    @patch("django.conf.settings.TWILIO_ACCOUNT_SID", "ACxxx")
    @patch("django.conf.settings.TWILIO_AUTH_TOKEN", "authxxx")
    @patch("django.conf.settings.TWILIO_FROM_PHONE", "+12345")
    def test_whatsapp_recipient_formatting(self):
        """
        Verify that WhatsApp recipient is correctly formatted with a leading '+'.
        """
        # Re-init service to pick up mocked twilio settings
        service = NotificationService()

        # Mock twilio message creation
        mock_messages = MagicMock()
        service.twilio_client.messages = mock_messages

        # Test with phone number missing +
        self.user.phone = "2348012345678"
        service._dispatch_phone_notification(self.user, "Body", "whatsapp")

        mock_messages.create.assert_called_with(
            body="Body", from_="whatsapp:+12345", to="whatsapp:+2348012345678"
        )
