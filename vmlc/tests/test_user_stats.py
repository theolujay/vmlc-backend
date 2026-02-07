from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from identity.models import Candidate, Staff, PreRegUser, User
from vmlc.models import Exam
from vmlc.utils.user import get_user_status_counts

class UserStatsRefactorTest(TestCase):
    def setUp(self):
        self.password = "password123"

    def create_user(self, email, is_active=True, last_login_days_ago=0):
        user = User.objects.create_user(
            email=email,
            password=self.password,
            first_name="Test",
            last_name="User",
            is_active=is_active
        )
        if last_login_days_ago is not None:
            user.last_login = timezone.now() - timedelta(days=last_login_days_ago)
            user.save()
        return user

    def create_candidate(self, user):
        return Candidate.objects.create(user=user, school_name="Test School")

    def create_staff(self, user, role=Staff.Roles.VOLUNTEER):
        return Staff.objects.create(user=user, role=role)

    def test_pre_registered_candidate_count(self):
        # Create a pre-registered user
        PreRegUser.objects.create(
            email="prereg@example.com",
            full_name="Pre Reg",
            phone="08012345678",
            interest_type=PreRegUser.InterestType.CANDIDATE
        )
        
        counts = get_user_status_counts(Candidate.objects.all(), "candidate")
        self.assertEqual(counts["pre_registered"], 1)
        self.assertEqual(counts["registered"], 0)

    def test_pre_registered_staff_count(self):
        # Create a pre-registered volunteer (staff)
        PreRegUser.objects.create(
            email="volunteer@example.com",
            full_name="Volunteer",
            phone="08012345678",
            interest_type=PreRegUser.InterestType.VOLUNTEER
        )

        counts = get_user_status_counts(Staff.objects.all(), "staff")
        self.assertEqual(counts["pre_registered"], 1)
        self.assertEqual(counts["registered"], 0)

    def test_registered_and_pre_registered_overlap(self):
        # User is both pre-registered and fully registered
        email = "both@example.com"
        PreRegUser.objects.create(
            email=email,
            full_name="Both",
            phone="08012345678",
            interest_type=PreRegUser.InterestType.CANDIDATE
        )
        
        user = self.create_user(email)
        self.create_candidate(user)
        
        counts = get_user_status_counts(Candidate.objects.all(), "candidate")
        
        # Should be registered
        self.assertEqual(counts["registered"], 1)
        # Should NOT be counted as pre-registered because they are already registered
        self.assertEqual(counts["pre_registered"], 0)
        # Should be counted in both_entities
        self.assertEqual(counts["both_entities"], 1)

    def test_model_status_property_simplification(self):
        # Create a user with pending verification (using a mock or actual UserVerification if it exists)
        user = self.create_user("pending@example.com", last_login_days_ago=1)
        candidate = self.create_candidate(user)
        
        from identity.models import UserVerification
        UserVerification.objects.create(user=user, is_pending=True)
        
        # Old logic would return "pending"
        # New logic should ignore verification and return "active" or "inactive"
        # For candidate, we need an exam to be "active"
        
        # Test Staff status which is simpler
        staff_user = self.create_user("staff_pending@example.com", last_login_days_ago=1)
        staff = self.create_staff(staff_user)
        UserVerification.objects.create(user=staff_user, is_pending=True)
        
        self.assertEqual(staff.status, "active")

    def test_active_candidate(self):
        # Active candidate: active user, logged in recently
        # Need an exam if candidates require it for 'active' status?
        # get_user_status_counts checks for last_concluded_exam
        # If no concluded exam, active is 0 for candidates.
        
        # Let's create a concluded exam
        exam = Exam.objects.create(
            scheduled_date=timezone.now() - timedelta(days=2),
            open_duration_hours=1,
            is_active=True
        )
        
        user = self.create_user("active@example.com", last_login_days_ago=1)
        candidate = self.create_candidate(user)
        
        # Candidate needs to have score in this exam
        from vmlc.models import CandidateExamResult
        CandidateExamResult.objects.create(candidate=candidate, exam=exam, score=10.0)

        counts = get_user_status_counts(Candidate.objects.all(), "candidate")
        self.assertEqual(counts["active"], 1)
        self.assertEqual(counts["inactive"], 0)
        self.assertEqual(counts["registered"], 1)

    def test_inactive_candidate_no_login(self):
        # Inactive: hasn't logged in recently
        user = self.create_user("inactive@example.com", last_login_days_ago=10)
        self.create_candidate(user)
        
        counts = get_user_status_counts(Candidate.objects.all(), "candidate")
        self.assertEqual(counts["active"], 0)
        self.assertEqual(counts["inactive"], 1)

    def test_deactivated_candidate(self):
        user = self.create_user("deactivated@example.com", is_active=False)
        self.create_candidate(user)
        
        counts = get_user_status_counts(Candidate.objects.all(), "candidate")
        self.assertEqual(counts["deactivated"], 1)
        self.assertEqual(counts["registered"], 1)
        self.assertEqual(counts["inactive"], 0) # Inactive calculation excludes deactivated

    def test_active_staff(self):
        # Staff doesn't need exam enrollment
        user = self.create_user("staffactive@example.com", last_login_days_ago=1)
        self.create_staff(user)
        
        counts = get_user_status_counts(Staff.objects.all(), "staff")
        self.assertEqual(counts["active"], 1)
        self.assertEqual(counts["registered"], 1)
