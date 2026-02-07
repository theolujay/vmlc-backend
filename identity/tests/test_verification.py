from unittest.mock import patch
import boto3
from moto import mock_aws
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_api_key.models import APIKey
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from identity.models import (
    Staff,
    UserVerification,
)

User = get_user_model()


class UserVerificationEndpointsTest(APITestCase):

    def setUp(self):
        self.api_key, self.key = APIKey.objects.create_key(name="test-key")
        self.client.credentials(HTTP_X_API_KEY=self.key)
        self.user = User.objects.create_user(
            email="testuser@example.com",
            password="password123",
            first_name="Test",
            last_name="User",
            is_email_verified=True,
        )
        self.client.force_authenticate(user=self.user)

    def test_get_user_verification_status(self):
        url = reverse("vmlc:user-verification-status")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @mock_aws
    def test_user_verification_upload(self):
        # Create a mock S3 bucket
        conn = boto3.resource("s3", region_name="us-east-1")
        conn.create_bucket(Bucket="vmlc-s3")

        url = reverse("vmlc:user-verification-upload")
        # Create a dummy file for upload
        dummy_file = SimpleUploadedFile(
            "test_id_card.pdf", b"file_content", content_type="application/pdf"
        )
        data = {"id_card": dummy_file}
        response = self.client.post(url, data, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)


class UserVerificationAdminEndpointsTest(APITestCase):

    def setUp(self):
        self.api_key, self.key = APIKey.objects.create_key(name="test-key")
        self.client.credentials(HTTP_X_API_KEY=self.key)
        self.manager_user = User.objects.create_user(
            email="manager@example.com",
            password="password123",
            first_name="Manager",
            last_name="User",
        )
        self.manager_profile = Staff.objects.create(
            user=self.manager_user, role=Staff.Roles.MANAGER
        )
        self.verification = UserVerification.objects.create(
            user=self.manager_user, is_approved=True
        )
        self.client.force_authenticate(user=self.manager_user)

        self.test_user = User.objects.create_user(
            email="testuser@example.com",
            password="password123",
            first_name="Test",
            last_name="User",
        )
        self.test_user_verification = UserVerification.objects.create(
            user=self.test_user, is_pending=True
        )

    def test_get_user_verification_list(self):
        url = reverse("vmlc:user-verification-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_verification_action(self):
        url = reverse(
            "vmlc:user-verification-action", kwargs={"user_id": self.test_user.id}
        )
        data = {"is_approved": True}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
