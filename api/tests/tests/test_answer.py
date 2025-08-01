## File: api/tests/test_answers.py
import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from api.models import Candidate, Staff, Exam, Question, CandidateScore

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def submit_exam_answers_url():
    def _dynamic_url(exam_id):
        return reverse("v1:api-submit-exam-answers", kwargs={"exam_id": exam_id})

    return _dynamic_url


@pytest.fixture
def create_logged_in_screening_candidate(api_client):
    def do_create(username="patrick", email="patrick@test.com", password="password123"):
        user = User.objects.create_user(
            username=username, email=email, password=password
        )
        candidate = Candidate.objects.create(user=user, role="screening")
        refresh = RefreshToken.for_user(candidate.user)
        api_client.force_authenticate(user=candidate.user)
        return candidate, str(refresh), str(refresh.access_token)

    return do_create


@pytest.mark.django_db
class TestSubmitExamAnswers:
    def test_candidate_submit_exam_answers_success(
        self, api_client, submit_exam_answers_url, create_logged_in_screening_candidate
    ):
        candidate, _, access = create_logged_in_screening_candidate()
        exam_data = {
            "stage": "screening",
            "title": "Screening Exam",
            "description": "Screening exam",
            "is_active": True,
            "open_duration_hours": 2,
            "countdown_minutes": 60,
        }
        exam = Exam.objects.create(**exam_data)
        question_1_data = {
            "text": "How many Newton's laws of motion are there?",
            "option_a": "4",
            "option_b": "3",
            "option_c": "5",
            "option_d": "1",
            "correct_answer": "B",
            "difficulty": "easy",
        }
        question_1 = Question.objects.create(
            text=question_1_data["text"],
            option_a=question_1_data["option_a"],
            option_b=question_1_data["option_b"],
            option_c=question_1_data["option_c"],
            option_d=question_1_data["option_d"],
            correct_answer=question_1_data["correct_answer"],
            difficulty=question_1_data["difficulty"],
        )
        question_2_data = {
            "text": "What's the total angle in a triangle??",
            "option_a": "400",
            "option_b": "360",
            "option_c": "50",
            "option_d": "180",
            "correct_answer": "D",
            "difficulty": "easy",
        }
        question_2 = Question.objects.create(
            text=question_2_data["text"],
            option_a=question_2_data["option_a"],
            option_b=question_2_data["option_b"],
            option_c=question_2_data["option_c"],
            option_d=question_2_data["option_d"],
            correct_answer=question_2_data["correct_answer"],
            difficulty=question_2_data["difficulty"],
        )
        candidate_answers_data = {
            "answers": [
                {"question": question_1.id, "selected_option": "B"},
                {"question": question_2.id, "selected_option": "D"},
            ]
        }
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        response = api_client.post(
            submit_exam_answers_url(exam.id), candidate_answers_data, format="json"
        )
        candidate_score, _ = CandidateScore.objects.get_or_create(
            candidate=candidate,
            exam=exam,
        )
        assert response.status_code == 200
        assert "Answers submitted!" in response.data["message"]

    def test_candidate_duplicate_submit_exam_answers_fail(
        self, api_client, submit_exam_answers_url, create_logged_in_screening_candidate
    ):
        _, _, access = create_logged_in_screening_candidate()
        exam_data = {
            "stage": "screening",
            "title": "Screening Exam",
            "description": "Screening exam",
            "is_active": True,
            "open_duration_hours": 2,
            "countdown_minutes": 60,
        }
        exam = Exam.objects.create(**exam_data)
        question_1_data = {
            "text": "How many Newton's laws of motion are there?",
            "option_a": "4",
            "option_b": "3",
            "option_c": "5",
            "option_d": "1",
            "correct_answer": "B",
            "difficulty": "easy",
        }
        question_1 = Question.objects.create(
            text=question_1_data["text"],
            option_a=question_1_data["option_a"],
            option_b=question_1_data["option_b"],
            option_c=question_1_data["option_c"],
            option_d=question_1_data["option_d"],
            correct_answer=question_1_data["correct_answer"],
            difficulty=question_1_data["difficulty"],
        )
        question_2_data = {
            "text": "What's the total angle in a triangle??",
            "option_a": "400",
            "option_b": "360",
            "option_c": "50",
            "option_d": "180",
            "correct_answer": "D",
            "difficulty": "easy",
        }
        question_2 = Question.objects.create(
            text=question_2_data["text"],
            option_a=question_2_data["option_a"],
            option_b=question_2_data["option_b"],
            option_c=question_2_data["option_c"],
            option_d=question_2_data["option_d"],
            correct_answer=question_2_data["correct_answer"],
            difficulty=question_2_data["difficulty"],
        )
        candidate_answers_data = {
            "answers": [
                {"question": question_1.id, "selected_option": "B"},
                {"question": question_2.id, "selected_option": "A"},
            ]
        }
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        api_client.post(
            submit_exam_answers_url(exam.id), candidate_answers_data, format="json"
        )
        response = api_client.post(
            submit_exam_answers_url(exam.id), candidate_answers_data, format="json"
        )
        assert response.status_code == 400
        assert (
            "You have already submitted answers for this exam."
            in response.data["message"]
        )
