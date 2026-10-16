from unittest.mock import patch

from django.test import RequestFactory, TestCase
from django.test.utils import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_api_key.models import APIKey

from identity.models import Candidate, User


class AuthEndpointsTest(APITestCase):
    def setUp(self):
        self.api_key, self.key = APIKey.objects.create_key(name="test-key")
        self.client.credentials(HTTP_X_API_KEY=self.key)
        self.user = User.objects.create_user(
            email="testuser@example.com",
            password="password123",
            first_name="Test",
            last_name="User",
        )

    def test_login(self):
        url = reverse("identity:login")
        data = {"email": "testuser@example.com", "password": "password123"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertNotIn("refresh", response.data)
        self.assertIn("refresh", response.cookies)


class LoginErrorTest(APITestCase):
    def setUp(self):
        self.api_key, self.key = APIKey.objects.create_key(name="test-key")
        self.client.credentials(HTTP_X_API_KEY=self.key)
        self.user = User.objects.create_user(
            email="testuser@example.com",
            password="password123",
            first_name="Test",
            last_name="User",
        )

    def test_login_invalid_password(self):
        url = reverse("identity:login")
        data = {"email": "testuser@example.com", "password": "wrongpassword"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["detail"], "Invalid email or password")

    def test_login_invalid_email(self):
        url = reverse("identity:login")
        data = {"email": "wronguser@example.com", "password": "password123"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["detail"], "Invalid email or password")


@override_settings(GOOGLE_OAUTH_CLIENT_ID="test-google-client-id")
class GoogleSignInTest(APITestCase):
    def setUp(self):
        _, self.key = APIKey.objects.create_key(name="test-google-key")
        self.client.credentials(HTTP_X_API_KEY=self.key)
        self.url = reverse("identity:google-sign-in")

    @patch("identity.views.auth.id_token.verify_oauth2_token")
    def test_google_sign_in_uses_existing_account(self, verify_token):
        user = User.objects.create_user(
            email="testuser@example.com",
            password="password123",
            first_name="Test",
            last_name="User",
        )
        verify_token.return_value = {
            "email": user.email,
            "email_verified": True,
        }

        response = self.client.post(
            self.url, {"credential": "google-id-token"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertNotIn("refresh", response.data)
        self.assertIn("refresh", response.cookies)
        verify_token.assert_called_once()

    @patch("identity.views.auth.id_token.verify_oauth2_token")
    def test_google_sign_in_does_not_create_unknown_accounts(self, verify_token):
        verify_token.return_value = {
            "email": "unknown@example.com",
            "email_verified": True,
        }

        response = self.client.post(
            self.url, {"credential": "google-id-token"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(User.objects.filter(email="unknown@example.com").exists())

class FirstLoginTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            email="test@example.com",
            password="!Testpassword234",
            first_name="Test",
            last_name="User",
            is_email_verified=False,
        )
        # Create a profile with created_by=None to simulate a self-registered user
        self.candidate = Candidate.objects.create(
            user=self.user,
            school_name="Test School",
            role=Candidate.Roles.SCREENING,
        )

    def test_first_login_sets_email_verified(self):
        # Ensure it's false initially
        self.assertFalse(self.user.is_email_verified)
        self.assertIsNone(self.user.last_login)

        # Simulate login
        self.client.login(email="test@example.com", password="!Testpassword234")

        # Reload user from DB
        self.user.refresh_from_db()

        # Check if email is verified
        self.assertTrue(
            self.user.is_email_verified,
            "is_email_verified should be True after first login",
        )
        self.assertIsNotNone(self.user.last_login)
