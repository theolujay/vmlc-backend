from django.test import TestCase
from vmlc.models import Question, Exam


class QuestionModelTest(TestCase):

    def test_create_question(self):
        question = Question.objects.create(
            text="What is the capital of France?",
            option_a="London",
            option_b="Paris",
            option_c="Berlin",
            option_d="Madrid",
            correct_answer="B",
        )
        self.assertEqual(question.text, "What is the capital of France?")
        self.assertEqual(question.correct_answer, "B")


class ExamModelTest(TestCase):

    def test_create_exam(self):

        exam = Exam.objects.create()

        self.assertIsNotNone(exam.id)
