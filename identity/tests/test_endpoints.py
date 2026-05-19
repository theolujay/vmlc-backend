from unittest.mock import patch
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_api_key.models import APIKey
from django.contrib.auth import get_user_model
from django.urls import reverse

from identity.models import Staff, UserVerification

User = get_user_model()


class ListEndpointsTest(APITestCase):

    def setUp(self):
        self.api_key, self.key = APIKey.objects.create_key(name="test-key")
        self.client.credentials(HTTP_X_API_KEY=self.key)
        self.staff_user = User.objects.create_user(
            email="staff@example.com",
            password="password123",
            first_name="Staff",
            last_name="User",
        )
        self.staff_profile = Staff.objects.create(
            user=self.staff_user, role=Staff.Roles.MODERATOR
        )
        # user verification is a deprecated feature, but let's
        # also test that it doesn't hamper regular operations
        self.verification = UserVerification.objects.create(
            user=self.staff_user, is_approved=False
        )
        self.client.force_authenticate(user=self.staff_user)

    def test_get_candidate_list(self):
        url = reverse("identity:candidate-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class InviteStaffTest(APITestCase):
    def setUp(self):
        self.api_key, self.key = APIKey.objects.create_key(name="test-key")
        self.client.credentials(HTTP_X_API_KEY=self.key)
        self.staff_user = User.objects.create_user(
            email="staff1@example.com",
            password="password123",
            first_name="Staff",
            last_name="User",
        )
        self.staff_profile = Staff.objects.create(
            user=self.staff_user, role=Staff.Roles.MANAGER
        )
        # same as above, user verification is deprecated
        self.verification = UserVerification.objects.create(
            user=self.staff_user, is_approved=False
        )

    @patch("identity.tasks.revoke_user_invite_task.apply_async")
    def test_invite_staff_success(self, _mock_task):
        self.client.force_authenticate(user=self.staff_user)
        url = reverse("identity:staff-invite")

        data = {
            "email": "staff2@gmail.com",
            "first_name": "New",
            "last_name": "Staff",
            "phone": "+2349021498980",
            "password": "testtesttest",
            "password2": "testtesttest",
            "occupation": "Virtual Assistant",
            "role": "moderator",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.data["message"], "Staff profile created, invite sent."
        )

    def test_invite_staff_invalid_role(self):
        self.client.force_authenticate(user=self.staff_user)
        url = reverse("identity:staff-invite")

        data = {
            "email": "staff2@gmail.com",
            "first_name": "New",
            "last_name": "Staff",
            "phone": "+2349021498980",
            "password": "testtesttest",
            "password2": "testtesttest",
            "occupation": "Virtual Assistant",
            "role": "manager",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 400)
