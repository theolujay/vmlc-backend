from datetime import timedelta

from django.db import models
from django.db.models import Avg
from django.utils import timezone

from .question import Question
from .staff import Staff


class Exam(models.Model):
    """
    Represents a collection of questions scheduled at a specific date for a stage of competition.
    """

    class Stages(models.TextChoices):
        SCREENING = "screening", "Screening"
        LEAGUE = "league", "League"

    stage = models.CharField(
        max_length=20, choices=Stages.choices, default=Stages.LEAGUE, db_index=True
    )
    title = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=False, db_index=True)
    exam_date = models.DateTimeField(
        blank=True, null=True, db_index=True
    )
    open_duration_hours = models.PositiveIntegerField(
        default=12
    )
    countdown_minutes = models.PositiveIntegerField(
        default=60
    )
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    questions = models.ManyToManyField(Question, blank=True)
    created_by = models.ForeignKey(
        Staff,
        blank=True,
        null=True,
        related_name="exams_created",
        on_delete=models.SET_NULL,
    )
    updated_by = models.ForeignKey(
        Staff,
        blank=True,
        null=True,
        related_name="exams_updated",
        on_delete=models.SET_NULL,
    )

    def __str__(self):
        return f"{self.title} ({self.id})"

    @classmethod
    def active_exams(cls):
        """
        Returns only exams marked as active.
        """
        return cls.objects.filter(is_active=True)

    @property
    def is_currently_open(self):
        """
        Exam is open only if it's active, and either:
        - exam_date is None (always open)
        - or current time is within open window
        """
        if not self.is_active:
            return False
        if self.exam_date is None:
            return True
        now = timezone.now()
        end_time = self.exam_date + timedelta(hours=self.open_duration_hours)
        return self.exam_date <= now <= end_time

    def get_question_count(self):
        """
        Returns the number of questions in the exam.
        """
        return self.questions.count()

    def get_average_score(self):
        """
        Calculates the average score for all submissions tied to this exam.
        """
        return self.scores.aggregate(avg_score=Avg("score"))["avg_score"]
