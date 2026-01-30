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

    name = models.CharField(max_length=64, blank=True)
    edition = models.PositiveIntegerField(db_index=True)
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
    description = models.TextField(blank=True)
    config = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def title(self):
        return self.get_type_display()

    def __str__(self):
        return f"{self.competition.edition} - {self.get_type_display()}"

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


class StageExam(models.Model):
    """
    Links an exam to a specific Competition Stage and holds its
    competition-specific configuration (e.g., round number).
    """

    competition_stage = models.ForeignKey(
        Stage, on_delete=models.CASCADE, related_name="stage_exams"
    )
    round = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Round within this stage (e.g., Week 1, Week 2 for League stages).",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Is this exam currently part of the active competition flow?",
    )
    config = models.JSONField(
        default=dict, blank=True, help_text="StageExam-specific config."
    )

    class Meta:
        constraints = [
            # Ensures a specific round in a stage only has ONE StageExam entry.
            # Example: You can't have two "Round 1" entries for the "Screening" or "Final" stage.
            models.UniqueConstraint(
                fields=["competition_stage", "round"],
                name="unique_round_per_stage",
                condition=models.Q(round__isnull=False),
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
    Official standings generated from a single exam for a competition.

    A Standings object is a presentation artifact derived from exam results.
    Exactly one Standings record should exist for a given published (competition, stage, round).
    The record should only point to a local vmlc.Exam (native execution) AND should be
    associated with an external facilitator via `facilitator_system`.

    Immutable principle: `StandingsEntry.exam_score` is the canonical score for the snapshot.
    Changes to the underlying exam results do not automatically mutate published standings.
    Regeneration must be explicit.
    """

    class Facilitator(models.TextChoices):
        VMLC = "vmlc", "VMLC"
        ESTURDI = "esturdi", "Esturdi"

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
    # provenance field
    facilitator_system = models.CharField(
        max_length=20,
        choices=Facilitator.choices,
        default=Facilitator.VMLC,
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
                fields=["exam"],
                condition=Q(exam__isnull=False),
                name="unique_standings_per_exam",
            ),
            models.UniqueConstraint(
                fields=["competition", "stage", "round"],
                condition=Q(is_published=True),
                name="one_published_standings_per_stage_round",
            ),
        ]
        indexes = [
            models.Index(fields=["competition", "stage", "round", "is_published"]),
        ]


class StandingsEntry(models.Model):
    """
    A single candidate's standing within a specific Standings for an exam.

    This is the canonical table for that exam snapshot. It is authoritative
    for competition display and progression logic, but not for raw exam evaluation.

    - exam_score: the snapshot score used for ranking (copied at generation time).
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
    tie_break_reason = models.CharField(
        max_length=128,
        null=True,
        blank=True,
        help_text="Optional explanation when tie-break applied.",
    )
    # TODO: change 'percentile' field to property and compute percentile dynamically
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
            models.Index(fields=["standings", "exam_score"]),
        ]


class AggregateLeaderboard(models.Model):
    """
    Materialized leaderboard for a stage across rounds (e.g., League table).
    Created/updated when Standings are published.
    """

    competition = models.ForeignKey("Competition", on_delete=models.PROTECT)
    stage = models.CharField(max_length=20, choices=Stage.Type.choices)
    as_of_round = models.PositiveSmallIntegerField(
        null=True, blank=True
    )  # e.g., Week 3
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["competition", "stage", "as_of_round"])]


class AggregateLeaderboardEntry(models.Model):
    """
    A single candidate's entry in a materialized AggregateLeaderboard.
    Tracks cumulative performance across multiple rounds within a stage.
    """

    leaderboard = models.ForeignKey(
        AggregateLeaderboard, related_name="entries", on_delete=models.CASCADE
    )
    candidate = models.ForeignKey("identity.Candidate", on_delete=models.CASCADE)
    candidate_competition = models.ForeignKey(
        "competition.CandidateCompetition",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    total_score = models.DecimalField(max_digits=10, decimal_places=2)
    overall_rank = models.PositiveIntegerField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["leaderboard", "overall_rank"]),
            models.Index(fields=["leaderboard", "candidate"]),
        ]
