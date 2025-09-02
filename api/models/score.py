from django.db import models
from django.utils import timezone

from .candidate import Candidate
from .exam import Exam
from .question import Question
from .staff import Staff


class CandidateScore(models.Model):
    """
    A score representing a candidate's performance in an exam.

    Links to candidate, exam, and submitting staff member.
    """

    candidate = models.ForeignKey(
        Candidate, on_delete=models.CASCADE, related_name="scores"
    )
    exam = models.ForeignKey(Exam, on_delete=models.PROTECT, related_name="scores")
    score = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    date_recorded = models.DateTimeField(default=timezone.now)
    date_updated = models.DateTimeField(auto_now=True)
    submitted_by = models.ForeignKey(
        Staff, on_delete=models.SET_NULL, null=True, blank=True
    )
    auto_score = models.BooleanField(default=False, db_index=True)

    class Meta:
        unique_together = ("candidate", "exam")
        ordering = ["-date_recorded"]

    def calculate_and_save_auto_score(self, submitted_answers):
        """
        Scores an exam based on a list of submitted answers, updates the
        instance, and saves it.

        Args:
            submitted_answers (list[CandidateAnswer]): A list of unsaved
                CandidateAnswer objects. This avoids a race condition by not
                re-querying the database within the transaction.
        """
        total_questions = self.exam.questions.count()
        if not total_questions:
            self.score = 0
        else:
            correct_count = sum(
                1
                for answer in submitted_answers
                if answer.selected_option == answer.question.correct_answer
            )
            score = (correct_count / total_questions) * 100
            self.score = round(score, 2)

        self.auto_score = True
        self.date_recorded = timezone.now()
        self.save()


class CandidateAnswer(models.Model):
    candidate_score = models.ForeignKey(
        CandidateScore, related_name="answers", on_delete=models.CASCADE
    )
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_option = models.CharField(
        max_length=1,
        choices=Question.Options.choices,
        blank=True,
        null=True,
    )
    answered_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["candidate_score", "question"],
                name="unique_answer_per_candidate_score",
            )
        ]

    def __str__(self):
        return f"Answer by {self.candidate_score.candidate.user.username} for Q{self.question.id}"