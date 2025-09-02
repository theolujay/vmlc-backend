from typing import List

from django.db import models

from .staff import Staff


class LeaderboardSnapshot(models.Model):
    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)
    data: models.JSONField = models.JSONField()

    published_by: models.ForeignKey = models.ForeignKey(
        Staff,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leaderboard_snapshots",
    )

    class Meta:
        ordering: List[str] = ["-created_at"]


class CandidateScoreSnapshot(models.Model):
    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)
    published_at: models.DateTimeField = models.DateTimeField(
        null=True, blank=True, db_index=True
    )
    data: models.JSONField = models.JSONField()

    published_by: models.ForeignKey = models.ForeignKey(
        Staff,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="candidate_score_snapshots",
    )

    class Meta:
        ordering: List[str] = ["-created_at"]
