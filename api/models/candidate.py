from django.db import models
from django.db.models import Avg, Count, Q, Sum

from .user import User, UserVerification


class CandidateManager(models.Manager):
    """
    Custom manager for the Candidate model.
    """

    def with_scores(self):
        """
        Annotate candidates with total, average, and count of exam scores,
        excluding scores from exams at the 'screening' stage.
        """
        from ..models import Exam

        return self.annotate(
            total_score=Sum(
                "scores__score", filter=Q(scores__exam__stage=Exam.Stages.LEAGUE)
            ),
            average_score=Avg(
                "scores__score", filter=Q(scores__exam__stage=Exam.Stages.LEAGUE)
            ),
            exams_taken=Count(
                "scores",
                filter=Q(scores__exam__stage=Exam.Stages.LEAGUE),
                distinct=True,
            ),
        )

    def with_complete_data(self):
        """
        Annotate candidates with scores and optimize related data fetching.
        """
        return (
            self.with_scores()
            .prefetch_related("scores__exam", "scores__submitted_by__user")
            .select_related("user")
        )

    def active(self):
        """
        Get only active candidates
        """
        return self.filter(user__is_active=True)

    def by_role(self, role):
        """
        Get active candidates by role
        """
        return self.filter(role=role, user__is_active=True)


class Candidate(models.Model):
    """
    Represents a student or participant in the exam system.
    Linked to a User, assigned a role, and tracks their profile and score history.
    """

    class Roles(models.TextChoices):
        SCREENING = "screening", "Screening"
        LEAGUE = "league", "League"
        FINAL = "final", "Final"
        WINNER = "winner", "Winner"

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="candidate_profile",
    )
    school = models.CharField(max_length=150)
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    role = models.CharField(
        max_length=15, choices=Roles.choices, default=Roles.SCREENING, db_index=True
    )

    objects = CandidateManager()  # type: ignore

    @property
    def is_active(self):
        """Reference the user's is_active status"""
        return self.user.is_active

    @property
    def profile_photo(self):
        """Get profile photo from UserVerification with error handling"""
        try:
            return self.user.verification.profile_photo
        except (AttributeError, UserVerification.DoesNotExist):
            return None

    @property
    def id_card(self):
        """
        Get ID card from UserVerification with error handling
        """
        try:
            return self.user.verification.id_card
        except (AttributeError, UserVerification.DoesNotExist):
            return None

    @property
    def school_result(self):
        """
        Get school result from UserVerification with error handling
        """
        try:
            return self.user.verification.verification_document
        except (AttributeError, UserVerification.DoesNotExist):
            return None

    @property
    def is_verified(self):
        """
        Check if user has verification and is verified
        """
        return hasattr(self.user, "verification") and self.user.verification.is_verified

    @property
    def score_data(self):
        """
        Returns score summary (total and average) if annotated via `with_scores()`.
        """
        if hasattr(self, "total_score"):
            return {
                "total_score": float(self.total_score or 0),
                "average_score": float(self.average_score or 0),
            }
        return None

    @property
    def is_winner(self):
        """
        Returns True if candidate has 'winner' role.
        """
        return self.role == self.Roles.WINNER

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.school}"

    @classmethod
    def active_candidates(cls):
        """
        Returns all currently active candidates.
        """
        return cls.objects.filter(user__is_active=True)

    @classmethod
    def candidates_by_role(cls, role):
        """
        Returns active candidates filtered by role.
        """
        return cls.objects.filter(role=role, user__is_active=True)

    def get_latest_score(self):
        """
        Returns the most recent score submitted for this candidate.
        """
        from .score import CandidateScore

        return self.scores.latest("date_recorded")

    def get_score_dict(self):
        """
        Returns a dictionary of total, average, and per-exam scores for this candidate.
        Uses annotated and prefetched data if available to avoid extra queries.
        """
        # Use annotated values if they exist
        total_score = getattr(self, "total_score", None)
        average_score = getattr(self, "average_score", None)

        # Use prefetched scores if they exist, otherwise query
        if (
            hasattr(self, "_prefetched_objects_cache")
            and "scores" in self._prefetched_objects_cache
        ):
            scores = self._prefetched_objects_cache["scores"]
        else:
            scores = self.scores.select_related(
                "exam", "submitted_by__user"
            ).all()

        # If total/average scores were not annotated, calculate them from the scores list
        if total_score is None and scores:
            total_score = sum(s.score for s in scores if s.score is not None)
        if average_score is None and scores:
            average_score = total_score / len(scores) if scores else 0

        return {
            "total_score": float(total_score) if total_score is not None else 0.0,
            "average_score": float(average_score) if average_score is not None else 0.0,
            "scores": [
                {
                    "exam_id": s.exam.id,
                    "exam_title": s.exam.title,
                    "score": float(s.score),
                    "date_recorded": s.date_recorded.isoformat(),
                    "submitted_by": (
                        s.submitted_by.user.get_full_name()
                        if s.submitted_by and s.submitted_by.user
                        else None
                    ),
                    "auto_score": s.auto_score,
                }
                for s in scores
            ],
        }

    class Meta:
        indexes = [
            models.Index(fields=["role"]),
            models.Index(fields=["school"]),
        ]
