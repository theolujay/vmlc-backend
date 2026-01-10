import io
from PIL import Image
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_api_key.models import APIKey
from vmlc.models import FeatureFlag, User, Candidate, Staff

def generate_photo_file(name='test.jpg'):
    file = io.BytesIO()
    image = Image.new('RGB', (100, 100))
    image.save(file, 'jpeg')
    file.name = name
    file.seek(0)
    return file

class RegistrationV2Tests(APITestCase):
    def setUp(self):
        # Create API Key
        self.api_key_name = "test-key"
        self.api_key_obj, self.api_key = APIKey.objects.create_key(name=self.api_key_name)
        
        # Enable feature flags
        FeatureFlag.objects.update_or_create(key="candidate_registration", defaults={"value": True})
        FeatureFlag.objects.update_or_create(key="staff_registration", defaults={"value": True})
        
        self.url = reverse("vmlc-v2:register")

    def test_registration_missing_api_key(self):
        data = {
            "user_type": "candidate",
            "first_name": "Test",
            "last_name": "User",
            "email": "test@example.com",
            "phone": "08012345678",
            "consent": "true",
            "state": "Lagos",
            "school_name": "Test School",
            "school_type": "public",
            "current_class": "SS1",
            "document_type": "NIN",
            "document": generate_photo_file(),
            "face_capture": generate_photo_file("face.jpg")
        }
        response = self.client.post(self.url, data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_candidate_registration_success(self):
        data = {
            "user_type": "candidate",
            "first_name": "Candidate",
            "last_name": "One",
            "email": "candidate1@example.com",
            "phone": "08012345678",
            "consent": "true",
            "state": "Lagos",
            "school_name": "Test School",
            "school_type": "public",
            "current_class": "SS1",
            "document_type": "NIN",
            "document": generate_photo_file(),
            "face_capture": generate_photo_file("face.jpg")
        }
        response = self.client.post(
            self.url, 
            data, 
            format='multipart', 
            HTTP_X_API_KEY=self.api_key
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email="candidate1@example.com").exists())
        self.assertTrue(Candidate.objects.filter(user__email="candidate1@example.com").exists())

    def test_volunteer_registration_success(self):
        data = {
            "user_type": "volunteer",
            "first_name": "Volunteer",
            "last_name": "One",
            "email": "volunteer1@example.com",
            "phone": "08087654321",
            "consent": "true",
            "state": "Abuja",
            "occupation": "Teacher",
            "document_type": "passport",
            "document": generate_photo_file(),
            "face_capture": generate_photo_file("face.jpg")
        }
        response = self.client.post(
            self.url, 
            data, 
            format='multipart', 
            HTTP_X_API_KEY=self.api_key
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email="volunteer1@example.com").exists())
        self.assertTrue(Staff.objects.filter(user__email="volunteer1@example.com").exists())

    def test_candidate_missing_fields(self):
        data = {
            "user_type": "candidate",
            "first_name": "Test",
            # missing last_name, email, etc.
        }
        response = self.client.post(
            self.url, 
            data, 
            format='multipart', 
            HTTP_X_API_KEY=self.api_key
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
            "document_type": "passport", # Invalid for candidate
            "document": generate_photo_file(),
            "face_capture": generate_photo_file("face.jpg")
        }
        response = self.client.post(
            self.url, 
            data, 
            format='multipart', 
            HTTP_X_API_KEY=self.api_key
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
            "face_capture": generate_photo_file("face.jpg")
        }
        
        response = self.client.post(
            self.url, 
            data, 
            format='multipart', 
            HTTP_X_API_KEY=self.api_key
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Check either field "document" or non_field_errors
        self.assertTrue("document" in response.data["errors"] or "non_field_errors" in response.data["errors"])

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
            "face_capture": generate_photo_file("face.jpg")
        }
        response = self.client.post(
            self.url, 
            data, 
            format='multipart', 
            HTTP_X_API_KEY=self.api_key
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Should have errors for occupation and phone (if not using defaults)
        self.assertTrue("occupation" in response.data["errors"] or "phone" in response.data["errors"])

    def test_registration_already_exists(self):
        # First registration
        self.test_candidate_registration_success()
        
        # Second registration with same email
        data = {
            "user_type": "candidate",
            "first_name": "Duplicate",
            "last_name": "User",
            "email": "candidate1@example.com",
            "phone": "08011112222",
            "consent": "true",
            "state": "Lagos",
            "school_name": "Other School",
            "school_type": "public",
            "current_class": "SS1",
            "document_type": "NIN",
            "document": generate_photo_file(),
            "face_capture": generate_photo_file("face.jpg")
        }
        response = self.client.post(
            self.url, 
            data, 
            format='multipart', 
            HTTP_X_API_KEY=self.api_key
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data["errors"])

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
            "face_capture": generate_photo_file("face.jpg")
        }
        response = self.client.post(
            self.url, 
            data, 
            format='multipart', 
            HTTP_X_API_KEY=self.api_key
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("consent", response.data["errors"])