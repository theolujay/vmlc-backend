from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from vmlc.models import User, UserVerification
from vmlc.storage_backends import PrivateMediaStorage, PublicMediaStorage


class StorageTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com",
            password="password",
            first_name="Test",
            last_name="User",
            phone="+2348012345678",
        )
        self.verification = UserVerification.objects.create(user=self.user)

    @override_settings(
        STORAGES={
            "default": {
                "BACKEND": "vmlc.storage_backends.PrivateMediaStorage",
            },
            "public": {
                "BACKEND": "vmlc.storage_backends.PublicMediaStorage",
            },
            "staticfiles": {
                "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
            },
        }
    )
    @patch("vmlc.storage_backends.PrivateMediaStorage._save")
    def test_private_storage_uses_private_media_storage(self, mock_save):
        mock_save.return_value = "test_path"
        dummy_file = SimpleUploadedFile("test.jpg", b"file_content", content_type="image/jpeg")

        self.verification.id_card = dummy_file
        self.verification.save()

        self.assertIsInstance(self.verification.id_card.storage, PrivateMediaStorage)
        self.assertIn("X-Amz-Algorithm", self.verification.id_card.url)
        self.assertIn("X-Amz-Credential", self.verification.id_card.url)
        self.assertIn("X-Amz-Signature", self.verification.id_card.url)

    @override_settings(
        STORAGES={
            "default": {
                "BACKEND": "vmlc.storage_backends.PrivateMediaStorage",
            },
            "public": {
                "BACKEND": "vmlc.storage_backends.PublicMediaStorage",
            },
            "staticfiles": {
                "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
            },
        }
    )
    @patch("vmlc.storage_backends.PublicMediaStorage._save")
    def test_public_storage_uses_public_media_storage(self, mock_save):
        mock_save.return_value = "test_path"
        dummy_file = SimpleUploadedFile("profile.jpg", b"file_content", content_type="image/jpeg")

        self.user.profile_picture = dummy_file
        self.user.save()

        self.assertIsInstance(self.user.profile_picture.storage, PublicMediaStorage)
        self.assertNotIn("AWSAccessKeyId", self.user.profile_picture.url)
        self.assertNotIn("Signature", self.user.profile_picture.url)
        self.assertNotIn("Expires", self.user.profile_picture.url)
# TODO: Fix S3 issue in tests in CI/CD pipeline