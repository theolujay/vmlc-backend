from django.db import models

from .staff import Staff


class Question(models.Model):
    """
    A question belonging to one or more exams. Includes text, difficulty, and staff author.
    """

    class Options(models.TextChoices):
        A = "A", "Option A"
        B = "B", "Option B"
        C = "C", "Option C"
        D = "D", "Option D"

    class Difficulty(models.TextChoices):
        EASY = "easy", "Easy"
        MEDIUM = "medium", "Medium"
        HARD = "hard", "Hard"

    text: models.TextField = models.TextField()
    option_a: models.CharField = models.CharField(max_length=255, blank=True)
    option_b: models.CharField = models.CharField(max_length=255, blank=True)
    option_c: models.CharField = models.CharField(max_length=255, blank=True)
    option_d: models.CharField = models.CharField(max_length=255, blank=True)
    correct_answer: models.CharField = models.CharField(
        max_length=1, choices=Options.choices
    )
    date_created: models.DateTimeField = models.DateTimeField(auto_now_add=True)
    date_updated: models.DateTimeField = models.DateTimeField(auto_now=True)
    created_by: models.ForeignKey = models.ForeignKey(
        Staff,
        blank=True,
        null=True,
        related_name="questions_created",
        on_delete=models.SET_NULL,
    )
    updated_by: models.ForeignKey = models.ForeignKey(
        Staff,
        blank=True,
        null=True,
        related_name="questions_updated",
        on_delete=models.SET_NULL,
    )
    difficulty: models.CharField = models.CharField(
        max_length=10,
        choices=Difficulty.choices,
        default=Difficulty.MEDIUM,
    )
    is_active: models.BooleanField = models.BooleanField(default=True, db_index=True)

    def __str__(self) -> str:
        return f"Q{self.id}: {self.text[:50]}..."
