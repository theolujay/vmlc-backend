# Architectural Review: VMLC Integration with Competition Engine

**Date:** 2026-01-28
**Status:** Proposed
**Context:** Integration of the core exam engine (`vmlc`) with a new competition management system (`competition`), focusing on clean boundaries, data flow, and lifecycle management.

## 1. Required Adaptations in `vmlc`

The `vmlc` app should remain primarily concerned with the definition, execution, and raw result capture of exams. It should be largely competition-agnostic in its core models.

### Model Changes

*   **`vmlc.Exam`**:
    *   **Remove**: `stage` and `round` fields. These fields create unnecessary coupling and redundancy with `competition.Stage` and the `competition.RankingSnapshot` `round` field. The "context" of an exam within a competition is owned by `competition`.
    *   **New Field (Optional but Recommended)**: `competition_identifier = models.CharField(max_length=255, blank=True, null=True, help_text="Optional identifier from the competition engine linking this exam to a competition context.")`. This allows `competition` to store a reference to the `vmlc.Exam` ID and optionally allows `vmlc` to know *if* it's enrollment of a competition, but without enforcing `competition`'s structure.
    *   **Status Management**: The current `@property status` is good for its domain.

*   **`vmlc.CandidateExamResult`**:
    *   **Keep as is**: This model correctly captures a candidate's raw performance on a specific exam. It serves as the primary source of truth for raw scores before they are transformed into `RankingSnapshot`.
    *   **Relationship to `Enrollment`**: `vmlc.CandidateExamResult` does *not* directly relate to `competition.Enrollment`. Eligibility for an exam should be resolved by the `competition` app *before* the exam is presented to the candidate. `competition` will use `Enrollment` to filter eligible participants for `RankingSnapshot` generation.
    *   **Relationship to `RankingSnapshot`/`RankingEntry`**: `vmlc.CandidateExamResult` is the *source* for `RankingEntry` records. There is a 1-to-many relationship where one `CandidateExamResult` can inform one `RankingEntry`. `RankingEntry` will copy the `score` from `CandidateExamResult`.

*   **`vmlc.LeaderboardSnapshot` & `vmlc.CandidateExamResultSnapshot`**:
    *   **Deprecate**: These models are superseded by `competition.RankingSnapshot`, `competition.RankingEntry`, `competition.AggregateLeaderboard`, and `competition.AggregateLeaderboardEntry`. The logic for generating these JSON blobs should be migrated to populate the new structured models in `competition`.

### `vmlc.Exam` Competition-Awareness

`vmlc.Exam` should remain largely **competition-agnostic**. Its role is to define, deliver, and score an assessment. The `competition` app then provides the *context* for that assessment (e.g., "this exam is the Screening Stage for Competition X").
The optional `competition_identifier` field would be a weak, unidirectional link, allowing `vmlc` to optionally store context but not rely on `competition` models directly.

## 2. Exam Lifecycle (End-to-End)

Here's the proposed lifecycle, clearly delineating ownership and source of truth:

1.  **Exam Creation (VMLC)**
    *   **App Owner**: `vmlc`
    *   **Source of Truth**: `vmlc.Exam`, `vmlc.Question`
    *   **Description**: An admin defines the exam questions, duration, and other parameters in `vmlc`.

2.  **Competition Configuration & Exam Assignment (Competition)**
    *   **App Owner**: `competition`
    *   **Source of Truth**: `competition.Competition`, `competition.Stage`, `competition.StageExam` (New Model - see below), `competition.Enrollment`
    *   **Description**: An admin links a `vmlc.Exam` to a specific `competition.Stage` and round, and configures eligibility rules.

3.  **Candidate Eligibility Resolution (Competition)**
    *   **App Owner**: `competition`
    *   **Source of Truth**: `competition.Enrollment`, `competition.CandidateStageProgress`
    *   **Description**: Based on competition rules, `competition` determines which `Candidate`s are eligible to take a specific `Exam` at a given time. This might involve updating `CandidateStageProgress` or a new `ExamAssignment` model.

4.  **Exam Execution (VMLC)**
    *   **App Owner**: `vmlc`
    *   **Source of Truth**: `vmlc.CandidateExamResult`, `vmlc.CandidateAnswer`
    *   **Description**: Eligible candidates take the exam. Their answers and raw scores are recorded. `vmlc` manages the UI, timers, and submission process.

5.  **Result Finalization (VMLC)**
    *   **App Owner**: `vmlc`
    *   **Source of Truth**: `vmlc.CandidateExamResult`
    *   **Description**: Once the exam window closes, `vmlc` triggers any auto-grading and finalizes `CandidateExamResult` scores. This step might be triggered by an admin or a scheduled task.

6.  **RankingSnapshot Generation (Competition)**
    *   **App Owner**: `competition`
    *   **Source of Truth**: `competition.RankingSnapshot`, `competition.RankingEntry`
    *   **Description**: An admin manually initiates the "Generate RankingSnapshot" process for a specific `competition.StageExam`. A `competition` service fetches finalized `vmlc.CandidateExamResult`s for that exam, applies competition-specific rules (e.g., active candidates only), ranks them, and populates `RankingSnapshot` and `RankingEntry`. This is an **immutable snapshot**.

7.  **Admin Publish RankingSnapshot (Competition)**
    *   **App Owner**: `competition`
    *   **Source of Truth**: `competition.RankingSnapshot.is_published`
    *   **Description**: An admin reviews the generated `RankingSnapshot` and explicitly marks them as `is_published=True`, making them visible to candidates.

8.  **Aggregate Leaderboard Update (Competition)**
    *   **App Owner**: `competition`
    *   **Source of Truth**: `competition.AggregateLeaderboard`, `competition.AggregateLeaderboardEntry`
    *   **Description**: Upon publishing new `RankingSnapshot`, a `competition` service is triggered to recalculate and update the `AggregateLeaderboard` (e.g., the total scores for the League stage) incorporating the newly published `RankingSnapshot`. This is also an **immutable snapshot** for a given point in time (e.g., "End of Round X").

## 3. RankingSnapshot Generation Contract (Service Layer)

This should be implemented as a service object or function within `competition.services`.

```python
# competition/services/ranking_generator.py

from django.db import transaction
from competition.models import (
    Competition, Stage, StageExam, Enrollment, RankingSnapshot, RankingEntry
)
from vmlc.models import Exam, CandidateExamResult # Source for raw scores

class RankingSnapshotGenerationError(Exception):
    pass

class RankingSnapshotGenerator:
    """
    Service to generate immutable RankingSnapshot and RankingEntry records
    for a given exam within a competition stage.
    """

    def __init__(self, stage_exam_id: uuid.UUID):
        self.stage_exam = StageExam.objects.select_related(
            'competition_stage__competition', 'vmlc_exam'
        ).get(id=stage_exam_id)
        self.competition = self.stage_exam.competition_stage.competition
        self.stage = self.stage_exam.competition_stage
        self.exam = self.stage_exam.vmlc_exam

    @transaction.atomic
    def generate_and_save_ranking(
        self,
        ranking_policy: str = 'dense_rank', # e.g., 'dense_rank', 'sequential_rank'
        tie_break_strategy: str = 'submission_time_asc', # e.g., 'submission_time_asc', 'random'
        absentee_score: float = 0.0,
        published_by_staff_id: uuid.UUID = None
    ) -> RankingSnapshot:
        """
        Generates RankingSnapshot and RankingEntry records from exam results.

        Args:
            ranking_policy: Defines how ranks are assigned (e.g., 'dense_rank').
            tie_break_strategy: How to resolve ties in score (e.g., 'submission_time_asc').
            absentee_score: Score to assign to candidates who were eligible but didn't submit.
            published_by_staff_id: Staff member initiating this generation.

        Returns:
            The newly created RankingSnapshot object.

        Raises:
            RankingSnapshotGenerationError: If validation fails or no results are found.
        """
        self._validate_preconditions()

        # 1. Fetch raw CandidateExamResults for the associated vmlc.Exam
        raw_results = CandidateExamResult.objects.filter(exam=self.exam).select_related(
            'candidate', 'candidate__user'
        )

        # 2. Identify all eligible candidates for this stage/exam
        eligible_candidate_ids = set(
            Enrollment.objects.filter(
                competition=self.competition,
                status=Enrollment.Status.ACTIVE # Only active participants
            ).values_list('candidate_id', flat=True)
        )

        # 3. Map results to eligible candidates, handle absentees
        candidate_scores = {} # {candidate_id: {'score': float, 'recorded_at': datetime}}
        for res in raw_results:
            if res.candidate_id in eligible_candidate_ids:
                candidate_scores[res.candidate_id] = {
                    'score': float(res.score),
                    'recorded_at': res.recorded_at
                }
        
        # Add absentees (eligible candidates without a result)
        for cand_id in eligible_candidate_ids:
            if cand_id not in candidate_scores:
                candidate_scores[cand_id] = {
                    'score': absentee_score,
                    'recorded_at': None # Mark as absent
                }

        if not candidate_scores:
            raise RankingSnapshotGenerationError(f"No eligible candidate results found for Exam {self.exam.id}.")

        # 4. Sort and Rank candidates
        sorted_candidates = sorted(
            candidate_scores.items(),
            key=lambda item: (
                item[1]['score'],
                item[1]['recorded_at'] if tie_break_strategy == 'submission_time_asc' else None
            ),
            reverse=True # Higher score first, then earlier submission time
        )

        ranking_entries_to_create = []
        previous_score = None
        current_rank = 0
        for idx, (candidate_id, data) in enumerate(sorted_candidates):
            score = data['score']
            if score != previous_score:
                current_rank = idx + 1 # Dense rank
            
            # Find Enrollment for FK
            enrollment = Enrollment.objects.filter(
                candidate_id=candidate_id, competition=self.competition
            ).first() # Should always exist if in eligible_candidate_ids

            ranking_entries_to_create.append(
                RankingEntry(
                    candidate_id=candidate_id,
                    enrollment=enrollment,
                    exam_score=score,
                    rank=current_rank,
                    # Percentile can be calculated after all ranks are determined, or dynamically
                    # ... add percentile calculation logic here if needed, requires total count
                )
            )
            previous_score = score

        # 5. Create RankingSnapshot record
        ranking = RankingSnapshot.objects.create(
            competition=self.competition,
            stage=self.stage.type, # Use the string type, as RankingSnapshot takes string
            round=self.stage_exam.round_number, # Assuming StageExam has round_number
            exam=self.exam,
            is_published=False, # Must be explicitly published
            meta={'generated_by': published_by_staff_id, 'policy': ranking_policy, 'tie_break': tie_break_strategy},
            # data_json is for denormalized export, not internal use. Leave blank.
        )
        
        # Assign ranking to entries and bulk create
        for entry in ranking_entries_to_create:
            entry.ranking_snapshot = ranking
        RankingEntry.objects.bulk_create(ranking_entries_to_create)

        return ranking

    def _validate_preconditions(self):
        """Internal validation before generating ranking."""
        if not self.exam.status == Exam.Status.CONCLUDED:
            raise RankingSnapshotGenerationError(f"Exam {self.exam.id} is not yet concluded.")
        # Add more validation, e.g., ensure no existing published ranking for this stage_exam

```

**Validation Rules:**
*   The `vmlc.Exam` must be in a `CONCLUDED` state.
*   No published `RankingSnapshot` should exist for the same `competition`, `stage`, `round` (enforced by unique constraint on `RankingSnapshot`).
*   All `CandidateExamResult` records must have a score.

**Ranking Policy:**
*   **Dense Rank**: If multiple candidates have the same score, they receive the same rank, and the next candidate receives the next available rank (e.g., 1, 2, 2, 3).
*   **Tie-breaking**: For candidates with identical scores and thus identical ranks, an optional tie-breaker (e.g., `recorded_at` for `CandidateExamResult`) can be applied to determine their display order within that rank. `submission_time_asc` is the default.

**Handling Absentees:**
*   Candidates who are `ACTIVE` in `Enrollment` for the relevant `Competition` but do not have a `CandidateExamResult` for the specific `Exam` will be assigned `absentee_score` (defaulting to 0.0) and will appear in the ranking. Their `recorded_at` will be `None`.

**Failure Modes & Invariants:**
*   **Failure**: If `exam` is not concluded, or if required related objects are missing, `RankingSnapshotGenerationError` is raised.
*   **Invariant**: `RankingSnapshot` and `RankingEntry` are immutable once created. Any change requires generating *new* ranking and marking the old one as superseded (e.g., an `is_superseded` flag on `RankingSnapshot` could be added if re-running is a frequent requirement).
*   **Invariant**: Raw exam results (`vmlc.CandidateExamResult`) are *never* mutated by this process.

## 4. What NOT to Do

*   **Logic that should NOT live in models**:
    *   **Complex business logic**: Models should primarily define data structure and basic constraints. The `RankingSnapshotGenerator` example demonstrates how complex ranking logic belongs in a service.
    *   **Cross-app concerns**: `vmlc.Exam` should not decide if it's a "Screening" or "League" exam in the context of the `Competition` app. This belongs to `competition`'s `StageExam`.

*   **Logic that should NOT live in views**:
    *   **Data transformation/aggregation**: Views should retrieve data and format it for presentation, not perform complex calculations like ranking or leaderboard aggregation. Delegate this to services.
    *   **Database write operations without transaction management**: Complex updates spanning multiple models should be encapsulated in services, ensuring atomicity via transactions.

*   **Data that should NOT be denormalized**:
    *   **Dynamic calculated values**: Values that can be reliably calculated from canonical sources should generally not be denormalized. Example: `RankingEntry.percentile` is likely better calculated dynamically from `RankingEntry.rank` and the total number of entries, rather than stored. However, `exam_score` *is* denormalized in `RankingEntry` because it's enrollment of the immutable snapshot and protects against retroactive changes to the source `CandidateExamResult`.

## 5. New Models or Services to Consider

### New Model: `competition.StageExam`
*   **Purpose**: To explicitly link a `vmlc.Exam` to a specific `competition.Stage` and provide competition-specific metadata for that exam instance. This replaces `vmlc.Exam.stage` and `vmlc.Exam.round` and fully decouples `vmlc` from `competition`'s stage logic.
*   **Justification**: This model serves as the critical bridge. It allows `competition` to define the schedule and context for a `vmlc.Exam` without modifying `vmlc.Exam` itself. It can store the `round_number` specific to the stage (e.g., "League Round 1").

```python
# competition/models.py (New Model)
class StageExam(models.Model):
    """
    Links a vmlc.Exam to a specific Competition Stage and holds its
    competition-specific configuration (e.g., round number).
    """
    competition_stage = models.ForeignKey(
        Stage,
        on_delete=models.CASCADE,
        related_name="stage_exams"
    )
    vmlc_exam = models.ForeignKey( # Renamed from 'exam' to be explicit
        "vmlc.Exam",
        on_delete=models.PROTECT, # Protect exam from deletion if linked
        related_name="competition_contexts"
    )
    round_number = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Round number within this stage (e.g., Week 1, Week 2 for League stages)."
    )
    is_active = models.BooleanField(default=True, help_text="Is this exam currently enrollment of the active competition flow?")
    config = models.JSONField(default=dict, blank=True, help_text="StageExam-specific config.")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["competition_stage", "vmlc_exam"],
                name="unique_exam_per_stage"
            ),
            # If a stage has rounds, ensure unique round per stage
            models.UniqueConstraint(
                fields=["competition_stage", "round_number"],
                name="unique_round_per_stage",
                condition=models.Q(round_number__isnull=False)
            )
        ]
```

### Service: `CompetitionEligibilityService`
*   **Purpose**: Determines which `Candidate`s are eligible to take a specific `StageExam`.
*   **Justification**: Centralizes complex eligibility rules (e.g., "must have passed Screening," "not eliminated," "is active in competition"). Can query `Enrollment` and `CandidateStageProgress`.
*   **Example Usage**: `eligibility_service.is_eligible(candidate, stage_exam) -> bool` or `eligibility_service.get_eligible_candidates(stage_exam) -> QuerySet[Candidate]`.

### Service: `CompetitionProgressionService`
*   **Purpose**: Manages the advancement or elimination of candidates between stages.
*   **Justification**: Based on `RankingSnapshot` results and `Stage` rules, this service updates `CandidateStageProgress` and `Enrollment` (e.g., changing status from `ACTIVE` to `ELIMINATED`).
*   **Example Usage**: `progression_service.process_stage_results(ranking_id)`.

## 6. Migration & Incremental Adoption

Given that no production leaderboard data exists yet, this is an opportune time for a clean cutover.

1.  **Phased Development**:
    *   **Phase 1 (Competition Models & Services)**: Implement `competition.StageExam`, `RankingSnapshotGenerator`, and the `AggregateLeaderboard` models/services in `competition`.
    *   **Phase 2 (VMLC Adaptations)**: Modify `vmlc.Exam` by removing `stage` and `round` fields (requires data migration to populate `StageExam`). Deprecate `vmlc.LeaderboardSnapshot` and related generation logic.

2.  **Data Migration for `vmlc.Exam`**:
    *   Create a Django data migration in `competition` to populate `StageExam` records from existing `vmlc.Exam` instances, using their `stage` and `round` fields.
    *   **Example (Conceptual Data Migration Logic)**:
        ```python
        # competition/migrations/00XX_create_stage_exams.py
        from django.db import migrations
        
        def create_stage_exams_from_vmlc_exams(apps, schema_editor):
            Competition = apps.get_model('competition', 'Competition')
            Stage = apps.get_model('competition', 'Stage')
            StageExam = apps.get_model('competition', 'StageExam')
            Exam = apps.get_model('vmlc', 'Exam') # Old VMLC Exam model
            
            # Assuming a default competition exists or is created
            default_competition, _ = Competition.objects.get_or_create(
                year=2026, defaults={'status': 'upcoming'}
            )
            
            # Map vmlc.Exam stages to competition.Stage types
            stage_type_map = {
                'screening': Stage.Type.SCREENING,
                'league': Stage.Type.LEAGUE,
                # Add 'final' if vmlc.Exam ever had it
            }

            for vmlc_exam in Exam.objects.all():
                stage_type = vmlc_exam.stage # From old vmlc.Exam field
                if stage_type in stage_type_map:
                    competition_stage, _ = Stage.objects.get_or_create(
                        competition=default_competition,
                        type=stage_type_map[stage_type],
                        defaults={'description': f'{stage_type.capitalize()} Stage', 'order': 1 if stage_type == 'screening' else 2} # Assign sensible defaults
                    )
                    StageExam.objects.create(
                        competition_stage=competition_stage,
                        vmlc_exam=vmlc_exam,
                        round_number=vmlc_exam.round
                    )

        class Migration(migrations.Migration):
            dependencies = [
                ('competition', '00XX_previous_migration'), # Depend on RankingSnapshot etc.
                ('vmlc', '00XX_previous_migration'), # Depend on vmlc.Exam
            ]
            operations = [
                migrations.RunPython(create_stage_exams_from_vmlc_exams),
            ]
        ```

3.  **Deprecate Old Logic**: Remove calls to `generate_leaderboard_snapshot_task` and `generate_results_snapshot_task` from `vmlc/tasks.py` and `vmlc/utils/functions.py`. The `vmlc.LeaderboardSnapshot` and `vmlc.CandidateExamResultSnapshot` models can be removed after confirming no other parts of the system rely on them directly (or keep them for a transition period but stop writing to them).

4.  **Admin UI/API Integration**: Update Django Admin or API endpoints to use the new `competition` models and services for managing exams within competition stages and publishing ranking. The "Publish RankingSnapshot" and "Generate RankingSnapshot" actions would be exposed here.

By following this approach, `vmlc` becomes a cleaner, more focused exam engine, and `competition` gains robust, auditable structures for managing competition results and leaderboards. This makes the system "boringly correct" and ready for future extensions like external facilitator integration.