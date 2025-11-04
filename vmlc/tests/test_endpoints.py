
import boto3
import responses
from moto import mock_aws
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from unittest.mock import patch

from vmlc.models import Staff, UserVerification
from vmlc.models import Candidate, Exam, Question, Staff, UserVerification

User = get_user_model()

from rest_framework_api_key.models import APIKey

from vmlc.models import FeatureFlag

class HealthCheckTest(APITestCase):

    def test_health_check(self):
        url = reverse('vmlc:health-check')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

class AuthEndpointsTest(APITestCase):

    def setUp(self):
        self.api_key, self.key = APIKey.objects.create_key(name="test-key")
        self.client.credentials(HTTP_X_API_KEY=self.key)
        FeatureFlag.objects.create(key="candidate_registration", value=True)
        self.user = User.objects.create_user(
            email='testuser@example.com',
            password='password123',
            first_name='Test',
            last_name='User'
        )

    def test_candidate_registration(self):
        url = reverse('vmlc:register-candidate')
        data = {
            'email': 'newcandidate@example.com',
            'first_name': 'New',
            'last_name': 'Candidate',
            'phone': '08012345678',
            'password': 'newpassword123',
            'password2': 'newpassword123',
            'school': 'New School',
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_login(self):
        url = reverse('vmlc:login')
        data = {
            'email': 'testuser@example.com',
            'password': 'password123'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

class ListEndpointsTest(APITestCase):

    def setUp(self):
        self.api_key, self.key = APIKey.objects.create_key(name="test-key")
        self.client.credentials(HTTP_X_API_KEY=self.key)
        self.staff_user = User.objects.create_user(
            email='staff@example.com',
            password='password123',
            first_name='Staff',
            last_name='User'
        )
        self.staff_profile = Staff.objects.create(user=self.staff_user, role=Staff.Roles.MODERATOR)
        self.verification = UserVerification.objects.create(user=self.staff_user, is_approved=True)
        self.client.force_authenticate(user=self.staff_user)

    def test_get_candidate_list(self):
        url = reverse('vmlc:candidate-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_staff_list(self):
        url = reverse('vmlc:staff-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

class ExamEndpointsTest(APITestCase):

    def setUp(self):
        self.api_key, self.key = APIKey.objects.create_key(name="test-key")
        self.client.credentials(HTTP_X_API_KEY=self.key)
        self.staff_user = User.objects.create_user(
            email='staff@example.com',
            password='password123',
            first_name='Staff',
            last_name='User'
        )
        self.staff_profile = Staff.objects.create(user=self.staff_user, role=Staff.Roles.ADMIN)
        self.verification = UserVerification.objects.create(user=self.staff_user, is_approved=True)
        self.client.force_authenticate(user=self.staff_user)
        self.question = Question.objects.create(text="Test Question", correct_answer='A')

    def test_create_exam(self):
        url = reverse('vmlc:exam-list')
        data = {
            'title': 'New Exam',
            'stage': 'league',
            'questions': [self.question.id]
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_get_exam_detail(self):
        exam = Exam.objects.create(title='Test Exam', stage=Exam.Stages.LEAGUE)
        url = reverse('vmlc:exam-detail', kwargs={'exam_id': exam.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_update_exam(self):
        exam = Exam.objects.create(title='Test Exam', stage=Exam.Stages.LEAGUE)
        url = reverse('vmlc:exam-detail', kwargs={'exam_id': exam.id})
        data = {
            'title': 'Updated Exam Title',
            'stage': 'screening',
            'questions': [self.question.id]
        }
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        exam.refresh_from_db()
        self.assertEqual(exam.title, 'Updated Exam Title')

    def test_delete_exam(self):
        exam = Exam.objects.create(title='Test Exam', stage=Exam.Stages.LEAGUE)
        url = reverse('vmlc:exam-detail', kwargs={'exam_id': exam.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

class QuestionEndpointsTest(APITestCase):

    def setUp(self):
        self.api_key, self.key = APIKey.objects.create_key(name="test-key")
        self.client.credentials(HTTP_X_API_KEY=self.key)
        self.staff_user = User.objects.create_user(
            email='staff@example.com',
            password='password123',
            first_name='Staff',
            last_name='User'
        )
        self.staff_profile = Staff.objects.create(user=self.staff_user, role=Staff.Roles.ADMIN)
        self.verification = UserVerification.objects.create(user=self.staff_user, is_approved=True)
        self.client.force_authenticate(user=self.staff_user)

    def test_create_question(self):
        url = reverse('vmlc:question-list')
        data = {
            'text': 'New Question',
            'correct_answer': 'A'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_get_question_detail(self):
        question = Question.objects.create(text='Test Question', correct_answer='A')
        url = reverse('vmlc:question-detail', kwargs={'question_id': question.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_update_question(self):
        question = Question.objects.create(text='Test Question', correct_answer='A')
        url = reverse('vmlc:question-detail', kwargs={'question_id': question.id})
        data = {
            'text': 'Updated Question Text',
            'correct_answer': 'B'
        }
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        question.refresh_from_db()
        self.assertEqual(question.text, 'Updated Question Text')

    def test_delete_question(self):
        question = Question.objects.create(text='Test Question', correct_answer='A')
        url = reverse('vmlc:question-detail', kwargs={'question_id': question.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)



class UserVerificationEndpointsTest(APITestCase):

    def setUp(self):
        self.api_key, self.key = APIKey.objects.create_key(name="test-key")
        self.client.credentials(HTTP_X_API_KEY=self.key)
        self.user = User.objects.create_user(
            email='testuser@example.com',
            password='password123',
            first_name='Test',
            last_name='User',
            is_email_verified=True
        )
        self.client.force_authenticate(user=self.user)

    def test_get_user_verification_status(self):
        url = reverse('vmlc:user-verification-status')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @mock_aws
    def test_user_verification_upload(self):
        # Create a mock S3 bucket
        conn = boto3.resource("s3", region_name="us-east-1")
        conn.create_bucket(Bucket="vmlc-s3")

        url = reverse('vmlc:user-verification-upload')
        # Create a dummy file for upload
        dummy_file = SimpleUploadedFile("test_id_card.pdf", b"file_content", content_type="application/pdf")
        data = {
            'id_card': dummy_file
        }
        response = self.client.post(url, data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

class UserVerificationAdminEndpointsTest(APITestCase):

    def setUp(self):
        self.api_key, self.key = APIKey.objects.create_key(name="test-key")
        self.client.credentials(HTTP_X_API_KEY=self.key)
        self.manager_user = User.objects.create_user(
            email='manager@example.com',
            password='password123',
            first_name='Manager',
            last_name='User'
        )
        self.manager_profile = Staff.objects.create(user=self.manager_user, role=Staff.Roles.MANAGER)
        self.verification = UserVerification.objects.create(user=self.manager_user, is_approved=True)
        self.client.force_authenticate(user=self.manager_user)

        self.test_user = User.objects.create_user(
            email='testuser@example.com',
            password='password123',
            first_name='Test',
            last_name='User'
        )
        self.test_user_verification = UserVerification.objects.create(user=self.test_user, is_pending=True)

    def test_get_user_verification_list(self):
        url = reverse('vmlc:user-verification-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_verification_action(self):
        url = reverse('vmlc:user-verification-action', kwargs={'user_id': self.test_user.id})
        data = {
            'is_approved': True
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

class DashboardEndpointsTest(APITestCase):

    def setUp(self):
        self.api_key, self.key = APIKey.objects.create_key(name="test-key")
        self.client.credentials(HTTP_X_API_KEY=self.key)
        self.candidate_user = User.objects.create_user(
            email='candidate@example.com',
            password='password123',
            first_name='Candidate',
            last_name='User'
        )
        self.candidate_profile = Candidate.objects.create(user=self.candidate_user, school='Test School')

        self.staff_user = User.objects.create_user(
            email='staff@example.com',
            password='password123',
            first_name='Staff',
            last_name='User'
        )
        self.staff_profile = Staff.objects.create(user=self.staff_user, role=Staff.Roles.MODERATOR)
        self.verification = UserVerification.objects.create(user=self.staff_user, is_approved=True)

    def test_get_candidate_dashboard(self):
        self.client.force_authenticate(user=self.candidate_user)
        url = reverse('vmlc:candidate-dashboard')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

    def test_get_staff_dashboard(self):
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('vmlc:staff-dashboard')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

class InviteStaffTest(APITestCase):
    def setUp(self):
        self.api_key, self.key = APIKey.objects.create_key(name="test-key")
        self.client.credentials(HTTP_X_API_KEY=self.key)
        self.staff_user = User.objects.create_user(
            email='staff1@example.com',
            password='password123',
            first_name='Staff',
            last_name='User'
        )
        self.staff_profile = Staff.objects.create(user=self.staff_user, role=Staff.Roles.MANAGER)
        self.verification = UserVerification.objects.create(user=self.staff_user, is_approved=True)

    @patch('vmlc.tasks.revoke_user_invite_task.apply_async')
    def test_invite_staff_success(self, mock_task):
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('vmlc:staff-invite')

        data = {
            "email": "staff2@gmail.com",
            "first_name": "New",
            "last_name": "Staff",
            "phone": "+2349021498980",
            "password": "testtesttest",
            "password2": "testtesttest",
            "occupation": "Virtual Assistant",
            "role": "moderator"
        }
        response = self.client.post(url, data, format='json')
        print(f"Status: {response.status_code}")
        print(f"Response: {response.data}")
        assert response.status_code == 201
        assert response.data["message"] == "Staff profile created, invite sent."
    
    def test_invite_staff_invalid_role(self):
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('vmlc:staff-invite')

        data = {
            "email": "staff2@gmail.com",
            "first_name": "New",
            "last_name": "Staff",
            "phone": "+2349021498980",
            "password": "testtesttest",
            "password2": "testtesttest",
            "occupation": "Virtual Assistant",
            "role": "manager"
        }
        response = self.client.post(url, data, format='json')
        print(f"Status: {response.status_code}")
        print(f"Response: {response.data}")
        assert response.status_code == 400
        # assert response.data["message"] == "Staff profile created, invite sent."