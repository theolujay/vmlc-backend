from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.utils import timezone
from datetime import timedelta
from identity.models import User, Candidate, Staff, PreRegUser
from vmlc.models import Event


class RegistrationMetricsViewTest(APITestCase):
    def setUp(self):
        self.password = "password123"
        self.staff_user = User.objects.create_user(
            email="admin@example.com",
            password=self.password,
            first_name="Admin",
            last_name="User",
        )
        self.staff_profile = Staff.objects.create(
            user=self.staff_user, role=Staff.Roles.ADMIN
        )
        self.client.force_authenticate(user=self.staff_user)
        self.url = reverse("vmlc:registration-trends")

    def test_get_registration_metrics_success(self):
        # Create some data
        now = timezone.now()

        # Pre-registrations
        PreRegUser.objects.create(
            full_name="Pre Reg 1",
            email="prereg1@example.com",
            phone="08011111111",
            interest_type=PreRegUser.InterestType.CANDIDATE,
            created_at=now - timedelta(days=1),
        )

        # Candidates (and their users)
        user1 = User.objects.create_user(
            email="cand1@example.com",
            password=self.password,
            first_name="Cand",
            last_name="One",
            date_joined=now - timedelta(days=1),
        )
        Candidate.objects.create(
            user=user1, school_name="School 1", created_at=now - timedelta(days=1)
        )

        # Events for funnel
        Event.objects.create(
            event_name="PRE_REGISTRATION", metadata={"interest_type": "candidate"}
        )
        Event.objects.create(
            event_name="PRE_REG_CONVERSION", metadata={"interest_type": "candidate"}
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data

        self.assertIn("daily", data)
        self.assertIn("weekly", data)
        self.assertIn("funnel", data)

        self.assertIn("total_users", data["daily"])
        self.assertIn("candidates", data["daily"])
        self.assertIn("pre_registrations", data["daily"])
        self.assertIn("staff", data["daily"])

        self.assertIn("overall", data["funnel"])
        self.assertIn("pre_registrations", data["funnel"]["overall"])
        self.assertIn("completed_registrations", data["funnel"]["overall"])
        self.assertIn("conversion_percentage", data["funnel"]["overall"])

        self.assertIn("candidate", data["funnel"])
        self.assertIn("volunteer", data["funnel"])

    def test_registration_metrics_query_params(self):
        response = self.client.get(self.url, {"days": 7, "weeks": 4})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
