from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from rest_framework_api_key.models import APIKey
from vmlc.models import PreRegUser, FeatureFlag, User

class PreRegistrationTestCase(APITestCase):
    def setUp(self):
        # Create API Key
        self.api_key_obj, self.api_key = APIKey.objects.create_key(name="Test Key")
        self.header = {"HTTP_X_API_KEY": self.api_key}
        
        # Ensure feature flag is open by default
        FeatureFlag.objects.create(key="pre_registration_open", value=True)
        
        self.url = reverse("vmlc-v2:pre-register")
        
        self.valid_payload = {
            "full_name": "Test User",
            "email": "test@example.com",
            "phone_number": "08012345678",
            "interest_type": "candidate"
        }

    def test_pre_registration_success_candidate(self):
        """Test successful pre-registration for a candidate."""
        response = self.client.post(self.url, self.valid_payload, **self.header)
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
        
        response = self.client.post(self.url, payload, **self.header)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(PreRegUser.objects.filter(interest_type="volunteer").count(), 1)

    def test_missing_api_key(self):
        """Test request without API key should fail."""
        response = self.client.post(self.url, self.valid_payload)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_missing_required_fields(self):
        """Test request with missing required fields."""
        required_fields = ["full_name", "email", "phone_number", "interest_type"]
        for field in required_fields:
            payload = self.valid_payload.copy()
            del payload[field]
            response = self.client.post(self.url, payload, **self.header)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn(field, response.data)

    def test_invalid_email(self):
        """Test request with invalid email format."""
        payload = self.valid_payload.copy()
        payload["email"] = "invalid-email"
        response = self.client.post(self.url, payload, **self.header)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_invalid_phone_number(self):
        """Test request with invalid phone number format."""
        payload = self.valid_payload.copy()
        payload["phone_number"] = "12345"
        response = self.client.post(self.url, payload, **self.header)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("phone_number", response.data)

    def test_duplicate_pre_registration_email(self):
        """Test that duplicate email in pre-registration returns 400, not 500."""
        # First registration
        self.client.post(self.url, self.valid_payload, **self.header)
        
        # Second registration with same email
        response = self.client.post(self.url, self.valid_payload, **self.header)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)
        # Check that we didn't create a second record
        self.assertEqual(PreRegUser.objects.count(), 1)

    def test_existing_user_email(self):
        """Test that an email already belonging to a User cannot pre-register."""
        User.objects.create_user(username="existing", email="test@example.com", password="pwd")
        
        response = self.client.post(self.url, self.valid_payload, **self.header)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_pre_registration_closed(self):
        """Test that pre-registration is blocked when feature flag is disabled."""
        FeatureFlag.objects.filter(key="pre_registration_open").update(value=False)
        
        response = self.client.post(self.url, self.valid_payload, **self.header)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
