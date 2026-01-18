from django.test import TestCase
from vmlc.serializers import CandidateRegistrationSerializer


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
