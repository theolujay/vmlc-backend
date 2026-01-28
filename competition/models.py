import uuid
from django.db import models
from django.db.models import Q


class Competition(models.Model):
    """
    Represents a single edition of the competition.
    Acts as the root aggregate for stages, exams, participation,
    and all competition-scoped configuration.
    """

    class Status(models.TextChoices):
        """Status of the competition"""

        UPCOMING = "upcoming", "Upcoming"
        ACTIVE = "active", "Active"
        CONCLUDED = "concluded", "Concluded"

    year = models.PositiveIntegerField(db_index=True)
    start_date = models.DateTimeField(null=True, blank=True, db_index=True)
    end_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        choices=Status.choices, default=Status.UPCOMING, db_index=True
    )
    config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Competition-level configuration flags and thresholds.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Stage(models.Model):
    """Phases inside a competition: Screening, League, Final"""

    class Type(models.TextChoices):
        """Types of stages"""

        SCREENING = "screening", "Screening"
        LEAGUE = "league", "League"
        FINAL = "final", "Final"

    competition = models.ForeignKey(
        "Competition", on_delete=models.CASCADE, related_name="stages"
    )
    type = models.CharField(choices=Type.choices, max_length=32)
    order = models.PositiveSmallIntegerField()
    description = models.TextField()
    config = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def title(self):
        return self.get_type_display()

    def __str__(self):
        return f"{self.competition.year} - {self.get_type_display()}"

    class Meta:
        ordering = ["order"]
        constraints = [
            models.UniqueConstraint(
                fields=["competition", "type"], name="unique_stage_per_competition"
            ),
            models.UniqueConstraint(
                fields=["competition", "order"],
                name="unique_stage_order_per_competition",
            ),
        ]


class CandidateCompetition(models.Model):
    """
    Represents a candidate's participation in a specific competition edition.

    This model tracks enrollment state, current stage placement,
    and competition-scoped metadata for a candidate.
    """

    class Status(models.TextChoices):
        # registered, not started
        ENROLLED = "enrolled", "Enrolled"
        # currently participating
        ACTIVE = "active", "Active"
        # removed by system rules and is terminal
        ELIMINATED = "eliminated", "Eliminated"
        # left voluntarily
        WITHDRAWN = "withdrawn", "Withdrawn"
         # forcibly removed due to violation
        DISQUALIFIED = "disqualified", "Disqualified"

    id = models.UUIDField(
        default=uuid.uuid4, unique=True, primary_key=True, editable=False
    )
    candidate = models.ForeignKey(
        "identity.Candidate", on_delete=models.CASCADE, related_name="competitions"
    )
    competition = models.ForeignKey(
        "Competition", on_delete=models.CASCADE, related_name="participants"
    )
    current_stage = models.ForeignKey(
        "Stage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="The candidate's current stage in the competition.",
    )
    status = models.CharField(
        choices=Status.choices, default=Status.ENROLLED, db_index=True
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    last_active_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Competition-specific data about the candidate.",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["candidate", "competition"],
                name="unique_candidate_per_competition",
            ),
        ]


class CandidateStageProgress(models.Model):
    """
    Tracks a candidate's progress and outcome within a specific stage
    of a competition.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED = "completed", "Completed"
        DISCONTINUED = "discontinued", "Discontinued"

    id = models.UUIDField(
        default=uuid.uuid4, unique=True, primary_key=True, editable=False
    )
    candidate_competition = models.ForeignKey(
        CandidateCompetition, on_delete=models.CASCADE, related_name="stage_progress"
    )
    stage = models.ForeignKey(Stage, on_delete=models.CASCADE)
    status = models.CharField(choices=Status.choices, default=Status.PENDING)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    discontinued_at = models.DateTimeField(null=True, blank=True)

    @property
    def is_terminal(self):
        return self.status in {
            self.Status.COMPLETED,
            self.Status.DISCONTINUED,
        }

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["candidate_competition", "stage"],
                name="unique_stage_progress_per_candidate",
            )
        ]


class Standings(models.Model):
    """
    Represents the official standings produced from a single exam within a competition.

    Standings are presentation artifacts derived from authoritative exam results.
    Exactly one Standings record exists per exam.

    - Screening: standings from the screening exam
    - League: weekly standings (one exam per round/week)
    - Final: standings from the final exam
    """

    competition = models.ForeignKey(
        "competition.Competition",
        on_delete=models.PROTECT,
        related_name="standings",
    )
    stage = models.CharField(
        max_length=20,
        choices=Stage.Type.choices,
        help_text="Competition stage this standings belongs to (screening, league, final).",
    )
    round = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        db_index=True,
        help_text="League round/week number. Null for screening and final.",
    )
    exam = models.ForeignKey(
        "vmlc.Exam",
        on_delete=models.PROTECT,
        help_text="Exam from which this standings was generated.",
    )
    is_published = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether this standings is visible to candidates.",
    )
    published_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
    )
    meta = models.JSONField(
        default=dict,
        blank=True,
        help_text="Auxiliary metadata (e.g. exam engine used: vmlc or esturdi).",
    )
    data_json = models.JSONField(
        null=True,
        blank=True,
        help_text="Optional denormalized export for caching or external consumption.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["competition", "stage", "round"],
                condition=Q(is_published=True),
                name="one_published_standings_per_stage_round",
            )
        ]


class StandingsEntry(models.Model):
    """
    Represents a candidate's ranked outcome within a single standings.

    This model is authoritative for competition display and progression logic,
    but not for raw exam evaluation.
    """

    standings = models.ForeignKey(
        Standings,
        related_name="entries",
        on_delete=models.PROTECT,
    )
    candidate = models.ForeignKey(
        "identity.Candidate",
        on_delete=models.CASCADE,
        related_name="standings_entries",
    )
    candidate_competition = models.ForeignKey(
        "competition.CandidateCompetition",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="standings_entries",
    )
    exam_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Candidate's exam score used for ranking.",
    )
    rank = models.PositiveIntegerField(
        null=True,
        blank=True,
        db_index=True,
    )
    percentile = models.FloatField(
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["standings", "candidate"], name="unique_candidate_per_standings"
            ),
        ]
        indexes = [
            models.Index(fields=["standings", "rank"]),
            models.Index(fields=["standings", "candidate"]),
        ]
