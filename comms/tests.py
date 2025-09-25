
import boto3
from moto import mock_aws
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model

from vmlc.models import Staff, UserVerification
from vmlc.models import Candidate, Exam, Question, Staff, UserVerification
from comms.models import Broadcast, BroadcastLog

User = get_user_model()

from rest_framework_api_key.models import APIKey

from vmlc.models import FeatureFlag

class BroadcastTest(APITestCase):
    
    def setUp(self):
        self.api_key, self.key = APIKey.objects.create_key(name="test-key")
        self.client.credentials(HTTP_X_API_KEY=self.key)
        self.staff_user = User.objects.create_user(
            email='staff@example.com',
            password='password123',
            first_name='Staff',
            last_name='User',
        )
        self.staff_profile = Staff.objects.create(user=self.staff_user, role=Staff.Roles.MANAGER)
        self.verification = UserVerification.objects.create(user=self.staff_user, is_verified=True)
        self.client.force_authenticate(user=self.staff_user)

    def test_create_broadcast(self):
        url = reverse('comms:broadcast')
        data = {
            "subject": "Test Subject",
            "message": "Test message...",
            "mediums": ["platform", "email"],
            "target_roles": ["league"]
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_list_broadcast(self):
        url = reverse('comms:broadcast')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
    def test_broadcast_detail(self):
        pass
    