
from django.test import TestCase
from django.contrib.auth import get_user_model
from vmlc.models import Candidate, Staff, Question, Exam

User = get_user_model()

class UserModelTest(TestCase):

    def test_create_user(self):
        user = User.objects.create_user(
            email='testuser@example.com',
            password='password123',
            first_name='Test',
            last_name='User'
        )
        self.assertEqual(user.email, 'testuser@example.com')
        self.assertTrue(user.check_password('password123'))
        self.assertEqual(user.get_full_name(), 'Test User')

    def test_create_superuser(self):
        superuser = User.objects.create_superuser(
            email='superuser@example.com',
            password='superpassword123',
            first_name='Super',
            last_name='User'
        )
        self.assertEqual(superuser.email, 'superuser@example.com')
        self.assertTrue(superuser.is_staff)
        self.assertTrue(superuser.is_superuser)

class CandidateModelTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            email='candidate@example.com',
            password='password123',
            first_name='Candidate',
            last_name='User'
        )

    def test_create_candidate(self):
        candidate = Candidate.objects.create(
            user=self.user,
            school='Test School'
        )
        self.assertEqual(candidate.user.email, 'candidate@example.com')
        self.assertEqual(candidate.school, 'Test School')
        self.assertEqual(str(candidate), 'Candidate User - Test School')

class StaffModelTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            email='staff@example.com',
            password='password123',
            first_name='Staff',
            last_name='User'
        )

    def test_create_staff(self):
        staff = Staff.objects.create(
            user=self.user,
            role=Staff.Roles.ADMIN
        )
        self.assertEqual(staff.user.email, 'staff@example.com')
        self.assertEqual(staff.role, 'admin')
        self.assertEqual(str(staff), 'Staff User (admin)')

class QuestionModelTest(TestCase):

    def test_create_question(self):
        question = Question.objects.create(
            text='What is the capital of France?',
            option_a='London',
            option_b='Paris',
            option_c='Berlin',
            option_d='Madrid',
            correct_answer='B'
        )
        self.assertEqual(question.text, 'What is the capital of France?')
        self.assertEqual(question.correct_answer, 'B')

class ExamModelTest(TestCase):

    def test_create_exam(self):
        exam = Exam.objects.create(
            title='Test Exam',
            stage=Exam.Stages.LEAGUE
        )
        self.assertEqual(exam.title, 'Test Exam')
        self.assertEqual(exam.stage, 'league')
