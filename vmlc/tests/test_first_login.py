from django.test import TestCase
from django.contrib.auth import get_user_model, login
from django.test import RequestFactory
from identity.models import Candidate, User

class FirstLoginTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            email="test@example.com",
            password="!Testpassword234",
            first_name="Test",
            last_name="User",
            is_email_verified=False
        )
        # Create a profile with created_by=None to simulate a self-registered user
        self.candidate = Candidate.objects.create(
            user=self.user,
            school_name="Test School",
            role=Candidate.Roles.SCREENING,
        )

    def test_first_login_sets_email_verified(self):
        # Ensure it's false initially
        self.assertFalse(self.user.is_email_verified)
        self.assertIsNone(self.user.last_login)

        # Simulate login
        # We need to use the client or manually trigger the signal if we want to be exact,
        # but client.login() should trigger the signal.
        self.client.login(email="test@example.com", password="!Testpassword234")
        
        # Reload user from DB
        self.user.refresh_from_db()
        
        # Check if email is verified
        # This currently should FAIL because created_by is None in the existing code.
        self.assertTrue(self.user.is_email_verified, "is_email_verified should be True after first login")
        self.assertIsNotNone(self.user.last_login)
