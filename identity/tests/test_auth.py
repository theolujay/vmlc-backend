from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_api_key.models import APIKey
from django.urls import reverse
from django.test import TestCase, RequestFactory

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
