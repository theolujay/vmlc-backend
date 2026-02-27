import io
from PIL import Image
from django.urls import reverse
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_api_key.models import APIKey

from identity.models import User, Candidate, Staff, PreRegUser
from vmlc.models import FeatureFlag
from vmlc.serializers import CandidateRegistrationSerializer


def generate_photo_file(name="test.jpg"):
    file = io.BytesIO()
    image = Image.new("RGB", (100, 100))
    image.save(file, "jpeg")
    file.name = name
    file.seek(0)
    return file


class CandidateRegistrationSerializerTest(TestCase):

    def test_valid_data(self):
        data = {
            "email": "newcandidate@example.com",
            "first_name": "New",
            "last_name": "Candidate",
            "phone": "08012345678",
            "password": "testpassword123",
            "password2": "testpassword123",
            "school_name": "New School",
        }
        serializer = CandidateRegistrationSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_password_mismatch(self):
        data = {
            "email": "newcandidate@example.com",
            "first_name": "New",
            "last_name": "Candidate",
            "phone": "08012345678",
            "password": "newpassword123",
            "password2": "wrongpassword",
            "school_name": "New School",
        }
        serializer = CandidateRegistrationSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("password2", serializer.errors)


class RegistrationV2Tests(APITestCase):
    def setUp(self):
        # Enable feature flags
        FeatureFlag.objects.update_or_create(
            key="candidate_registration", defaults={"value": True}
        )
        FeatureFlag.objects.update_or_create(
            key="staff_registration", defaults={"value": True}
        )

        self.url = reverse("vmlc-v2:register")

    def test_candidate_missing_fields(self):
        data = {
            "user_type": "candidate",
            "first_name": "Test",
            # missing last_name, email, etc.
        }
        response = self.client.post(
            self.url,
            data,
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_document_type(self):
        data = {
            "user_type": "candidate",
            "first_name": "Candidate",
            "last_name": "Two",
            "email": "candidate2@example.com",
            "phone": "08012345678",
            "consent": "true",
            "state": "Lagos",
            "school_name": "Test School",
            "school_type": "public",
            "current_class": "SS1",
            "document_type": "passport",  # Invalid for candidate
            "document": generate_photo_file(),
            "face_capture": generate_photo_file("face.jpg"),
        }
        response = self.client.post(
            self.url,
            data,
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("document_type", response.data["errors"])

    def test_candidate_registration_invalid_file_format(self):
        file = io.BytesIO(b"not an image")
        file.name = "test.txt"
        data = {
            "user_type": "candidate",
            "first_name": "Test",
            "last_name": "User",
            "email": "invalidfile@example.com",
            "phone": "08012345678",
            "consent": "true",
            "state": "Lagos",
            "school_name": "Test School",
            "school_type": "public",
            "current_class": "SS1",
            "document_type": "NIN",
            "document": file,
            "face_capture": generate_photo_file("face.jpg"),
        }

        response = self.client.post(
            self.url,
            data,
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Check either field "document" or non_field_errors
        self.assertTrue(
            "document" in response.data["errors"]
            or "non_field_errors" in response.data["errors"]
        )

    def test_volunteer_missing_fields(self):
        data = {
            "user_type": "volunteer",
            "first_name": "Volunteer",
            "last_name": "One",
            "email": "v_missing@example.com",
            # missing occupation, phone, etc.
            "consent": "true",
            "state": "Abuja",
            "document_type": "passport",
            "document": generate_photo_file(),
            "face_capture": generate_photo_file("face.jpg"),
        }
        response = self.client.post(
            self.url,
            data,
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Should have errors for occupation and phone (if not using defaults)
        self.assertTrue(
            "occupation" in response.data["errors"]
            or "phone" in response.data["errors"]
        )

    def test_registration_no_consent(self):
        data = {
            "user_type": "candidate",
            "first_name": "No",
            "last_name": "Consent",
            "email": "noconsent@example.com",
            "phone": "08033334444",
            "consent": "false",
            "state": "Lagos",
            "school_name": "Test School",
            "school_type": "public",
            "current_class": "SS1",
            "document_type": "NIN",
            "document": generate_photo_file(),
            "face_capture": generate_photo_file("face.jpg"),
        }
        response = self.client.post(
            self.url,
            data,
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("consent", response.data["errors"])


class PreRegistrationTestCase(APITestCase):
    def setUp(self):
        self.url = reverse("vmlc-v2:pre-register")

        self.valid_payload = {
            "full_name": "Test User",
            "email": "test@example.com",
            "phone": "08012345678",
            "interest_type": "candidate",
        }

    def test_pre_registration_success_candidate(self):
        """Test successful pre-registration for a candidate."""
        response = self.client.post(self.url, self.valid_payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(PreRegUser.objects.count(), 1)
        user = PreRegUser.objects.first()
        self.assertEqual(user.email, "test@example.com")
        self.assertEqual(user.interest_type, "candidate")

    def test_pre_registration_success_volunteer(self):
        """Test successful pre-registration for a volunteer."""
        payload = self.valid_payload.copy()
        payload["interest_type"] = "volunteer"
        payload["email"] = "volunteer@example.com"

        response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            PreRegUser.objects.filter(interest_type="volunteer").count(), 1
        )

    def test_missing_required_fields(self):
        """Test request with missing required fields."""
        required_fields = ["full_name", "email", "phone", "interest_type"]
        for field in required_fields:
            payload = self.valid_payload.copy()
            del payload[field]
            response = self.client.post(self.url, payload)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn(field, response.data["errors"])

    def test_invalid_email(self):
        """Test request with invalid email format."""
        payload = self.valid_payload.copy()
        payload["email"] = "invalid-email"
        response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data["errors"])

    def test_invalid_phone(self):
        """Test request with invalid phone number format."""
        payload = self.valid_payload.copy()
        payload["phone"] = "12345"
        response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("phone", response.data["errors"])

    def test_duplicate_pre_registration_email(self):
        """Test that duplicate email in pre-registration returns 400, not 500."""
        # First registration
        self.client.post(self.url, self.valid_payload)

        # Second registration with same email
        response = self.client.post(self.url, self.valid_payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data["errors"])
        # Check that we didn't create a second record
        self.assertEqual(PreRegUser.objects.count(), 1)

    def test_existing_user_email(self):
        """Test that an email already belonging to a User cannot pre-register."""
        User.objects.create_user(
            username="existing", email="test@example.com", password="pwd"
        )

        response = self.client.post(self.url, self.valid_payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data["errors"])
