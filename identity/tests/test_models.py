from django.test import TestCase

from identity.models import Candidate, Staff, User


class UserModelTest(TestCase):
    def test_create_user(self):
        user = User.objects.create_user(
            email="testuser@example.com",
            password="password123",
            first_name="Test",
            last_name="User",
        )
        self.assertEqual(user.email, "testuser@example.com")
        self.assertTrue(user.check_password("password123"))
        self.assertEqual(user.get_full_name(), "Test User")

    def test_create_superuser(self):
        superuser = User.objects.create_superuser(
            email="superuser@example.com",
            password="superpassword123",
            first_name="Super",
            last_name="User",
        )
        self.assertEqual(superuser.email, "superuser@example.com")
        self.assertTrue(superuser.is_staff)
        self.assertTrue(superuser.is_superuser)


class CandidateModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="candidate@example.com",
            password="password123",
            first_name="Candidate",
            last_name="User",
        )

    def test_create_candidate(self):
        candidate = Candidate.objects.create(user=self.user, school_name="Test School")
        self.assertEqual(candidate.user.email, "candidate@example.com")
        self.assertEqual(candidate.school_name, "Test School")
        self.assertEqual(str(candidate), "Candidate User - Test School")


class StaffModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="staff@example.com",
            password="password123",
            first_name="Staff",
            last_name="User",
        )

    def test_create_staff(self):
        staff = Staff.objects.create(user=self.user, role=Staff.Roles.ADMIN)
        self.assertEqual(staff.user.email, "staff@example.com")
        self.assertEqual(staff.role, "admin")
        self.assertEqual(str(staff), "Staff User (admin)")
