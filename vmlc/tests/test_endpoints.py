from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_api_key.models import APIKey

from django.contrib.auth import get_user_model
from django.urls import reverse

from identity.models import (
    Staff,
    UserVerification,
)

from vmlc.models import (
    Exam,
    Question,
)

User = get_user_model()


class HealthCheckTest(APITestCase):

    def test_health_check(self):
        url = reverse("vmlc:health-check")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class ExamEndpointsTest(APITestCase):

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
            user=self.staff_user, role=Staff.Roles.ADMIN
        )
        self.verification = UserVerification.objects.create(
            user=self.staff_user, is_approved=False
        )
        self.client.force_authenticate(user=self.staff_user)
        self.question = Question.objects.create(
            text="Test Question", correct_answer="A"
        )

    def test_create_exam(self):
        url = reverse("vmlc:exam-list")
        data = {"description": "New Exam Description", "questions": [self.question.id]}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_get_exam_detail(self):
        exam = Exam.objects.create()
        url = reverse("vmlc:exam-detail", kwargs={"exam_id": exam.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_update_exam(self):
        exam = Exam.objects.create()
        url = reverse("vmlc:exam-detail", kwargs={"exam_id": exam.id})
        data = {
            "description": "Updated Exam Description",
            "questions": [self.question.id],
        }
        response = self.client.put(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        exam.refresh_from_db()
        self.assertEqual(exam.description, "Updated Exam Description")

    def test_delete_exam(self):
        exam = Exam.objects.create()
        url = reverse("vmlc:exam-detail", kwargs={"exam_id": exam.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)


class QuestionEndpointsTest(APITestCase):

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
            user=self.staff_user, role=Staff.Roles.ADMIN
        )
        self.verification = UserVerification.objects.create(
            user=self.staff_user, is_approved=False
        )
        self.client.force_authenticate(user=self.staff_user)

    def test_create_question(self):
        url = reverse("vmlc:question-list")
        data = {"text": "New Question", "correct_answer": "A"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_get_question_detail(self):
        question = Question.objects.create(text="Test Question", correct_answer="A")
        url = reverse("vmlc:question-detail", kwargs={"question_id": question.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_update_question(self):
        question = Question.objects.create(text="Test Question", correct_answer="A")
        url = reverse("vmlc:question-detail", kwargs={"question_id": question.id})
        data = {"text": "Updated Question Text", "correct_answer": "B"}
        response = self.client.put(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        question.refresh_from_db()
        self.assertEqual(question.text, "Updated Question Text")

    def test_delete_question(self):
        question = Question.objects.create(text="Test Question", correct_answer="A")
        url = reverse("vmlc:question-detail", kwargs={"question_id": question.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)



