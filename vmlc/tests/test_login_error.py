from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_api_key.models import APIKey
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()

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
        url = reverse("vmlc:login")
        data = {"email": "testuser@example.com", "password": "wrongpassword"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["detail"], "Invalid email or password")

    def test_login_invalid_email(self):
        url = reverse("vmlc:login")
        data = {"email": "wronguser@example.com", "password": "password123"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["detail"], "Invalid email or password")
