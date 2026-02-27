from unittest.mock import patch
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_api_key.models import APIKey
from django.contrib.auth import get_user_model
from django.urls import reverse

from competition.models import Competition, Enrollment
from identity.models import Candidate, CowrywiseKidProfile, Staff, UserVerification

User = get_user_model()


class CowrywiseKidProfileTest(APITestCase):

    def setUp(self):
        self.api_key, self.key = APIKey.objects.create_key(name="test-key")
        self.client.credentials(HTTP_X_API_KEY=self.key)
        self.candidate_user = User.objects.create_user(
            email="candidate@example.com",
            password="password123",
            first_name="Candidate",
            last_name="User",
        )
        self.candidate_profile = Candidate.objects.create(
            user=self.candidate_user, role=Candidate.Roles.SCREENING
        )
        self.competition = Competition.objects.create(
            name="Test Competition",
            edition=1,
            status=Competition.Status.ACTIVE,
        )
        self.candidate_enrollment = Enrollment.objects.create(
            candidate=self.candidate_profile,
            competition=self.competition,
        )
        self.client.force_authenticate(user=self.candidate_user)

    def test_create_cowrywisekid_profile_success(self):
        url = reverse("identity:cowrywise-kids")
        data = {"username": "candidate0.vmlc@mailsac.com"}
        response = self.client.post(
            url,
            data,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        cowrywise_kid_profile, created = CowrywiseKidProfile.objects.get_or_create(
            username=data["username"],
            candidate=self.candidate_profile,
            defaults={
                "username": data["username"],
                "candidate": self.candidate_profile,
            },
        )
        self.assertEqual(created, False)
        self.assertEqual(self.candidate_profile, cowrywise_kid_profile.candidate)
