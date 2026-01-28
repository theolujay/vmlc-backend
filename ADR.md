# Architectural Review: Competition Models & VMLC Integration

**Date:** 2026-01-28
**Status:** Proposed
**Context:** Separation of concerns between Exam Engine (`vmlc`) and Competition Management (`competition`).

## 1. Model Analysis

### Competition App (`competition/models.py`)

*   **`Competition`**: Correctly acts as the root aggregate.
    *   *Responsibility*: Configuration, lifecycle (active/concluded), and scope.
    *   *Assessment*: Good. No changes needed.

*   **`Stage`**: Defines the structure (Screening, League, Final).
    *   *Responsibility*: Structural metadata and ordering.
    *   *Assessment*: Good. The `config` JSONField is useful for stage-specific rules (e.g., "drop lowest score").

*   **`CandidateCompetition`**: Enrollment record.
    *   *Responsibility*: Links `Identity` to `Competition`. Tracks global status (Eliminated vs Active).
    *   *Assessment*: **Crucial Missing Link**. It currently links `candidate` (from identity) but `vmlc` results link to `candidate` too. This is fine, but we must ensure that when `Standings` are generated, we only include candidates who are `ACTIVE` in this model.

*   **`CandidateStageProgress`**: Tracks state within a stage.
    *   *Responsibility*: Granular progress (e.g., "Did they finish Screening?").
    *   *Assessment*: The commented-out `# last_exam` suggests uncertainty.
    *   *Recommendation*: This should track *aggregate* status for the stage (e.g., "Qualified for Next Stage"). It should NOT link to a specific exam; `Standings` covers that.

*   **`Standings` & `StandingsEntry`**: The core presentation artifacts.
    *   *Responsibility*: Immutable snapshot of performance for a *single exam*.
    *   *Assessment*: Excellent pattern. It decouples "taking the test" (vmlc) from "ranking the users" (competition).
    *   *Gap*: There is no model for **Aggregate Leaderboards** (e.g., "League Table" summing up 10 weeks). `Standings` is per-exam. Relying on summing `StandingsEntry` on the fly is expensive and risky for consistency.

### VMLC App (`vmlc/models.py`)

*   **`Exam`**: The test definition.
    *   *Issue*: It has `stage` and `round` fields.
    *   *Violation*: `vmlc` shouldn't know about "League" vs "Screening" intimately.
    *   *Mitigation*: Keep them for now as "tags" for the engine, but `competition.Standings` is the authoritative mapper of "This Exam ID = League Round 1".

*   **`LeaderboardSnapshot`** (Legacy):
    *   *Status*: **Deprecated**. This stores a massive JSON blob. It should be replaced by `competition.Standings`.

## 2. Integration & Data Flow

### The "Publishing" Flow

1.  **Exam Execution (VMLC)**
    *   Candidates take `Exam`.
    *   `CandidateExamResult` records are created/updated.
    *   *No competition logic happens here.*

2.  **Result Finalization (Transition)**
    *   Exam `scheduled_date` + `duration` passes.
    *   An admin (or cron) triggers **"Finalize Results"**.
    *   *Action*: Calculate all pending scores (auto-grading).

3.  **Standings Generation (Competition)**
    *   **Trigger**: Explicit Admin Action "Publish Standings" for Exam X.
    *   **Input**: `vmlc.CandidateExamResult` for Exam X.
    *   **Process**:
        *   Fetch all results.
        *   Filter out disqualified/withdrawn candidates (via `CandidateCompetition`).
        *   Sort by Score (DESC), then Time (ASC).
        *   Calculate Rank and Percentile.
        *   **Write**: Create `Standings` (parent) and `StandingsEntry` (rows).
    *   **Output**: A frozen, queryable table in `competition` DB.

4.  **Aggregate Leaderboard Update (Competition)**
    *   *New Step*: Update the "League Table".
    *   **Input**: All published `Standings` for the current Stage.
    *   **Process**: Sum scores per candidate.
    *   **Write**: Update a `Leaderboard` model (see recommendations).

## 3. Boundary Violations & Risks

*   **Hidden Coupling via Strings**: `vmlc.Exam.stage` is a string that mimics `competition.Stage.type`. If we rename "League" to "Regular Season" in one place, the other breaks.
    *   *Fix*: Treat `vmlc.Exam.stage` as a "category" only. `competition` maps it authoritatively.
*   **Legacy Snapshots**: `vmlc` contains `generate_leaderboard_snapshot` logic that bakes in business rules (formatting, ranking). This logic must move to `competition`.
*   **Data Leakage**: `StandingsEntry` duplicates `exam_score`.
    *   *Verdict*: **Acceptable**. This is a snapshot. If the exam is re-graded later, the *published* standing should not change automatically. It requires a "Regenerate" action.

## 4. Recommended Refinements

### Priority 1: Implement the "Generator" Service
Move the logic from `vmlc.utils.functions._build_leaderboard_entries` into a new `competition` service.

```python
# competition/services.py (Conceptual)
def generate_standings(exam_id):
    # 1. Get raw results from VMLC
    results = CandidateExamResult.objects.filter(exam_id=exam_id)
    
    # 2. Filter by active participants in THIS competition
    # (Prevents old/rogue users from appearing)
    
    # 3. Calculate Ranks
    # 4. Bulk Create StandingsEntry
```

### Priority 2: Add `AggregateLeaderboard` Model
`Standings` is for a single exam. The "League Table" is long-lived.

```python
class AggregateLeaderboard(models.Model):
    """
    Sum of scores for a Stage (e.g. League Total).
    Updated every time a generic Standings is published.
    """
    competition = ForeignKey(...)
    stage = ForeignKey(...) 
    # Snapshotting the aggregate allows showing "Week 3 vs Week 4" progress
    as_of_round = IntegerField() 
    
class AggregateEntry(models.Model):
    leaderboard = ForeignKey(...)
    candidate = ForeignKey(...)
    total_score = DecimalField(...)
    overall_rank = IntegerField(...)
```

### Priority 3: Explicit "Source" Meta
Update `Standings` to explicitly handle external sources (Esturdi).

```python
class Standings(models.Model):
    # ... existing fields ...
    source_system = models.CharField(choices=["vmlc", "esturdi"], default="vmlc")
    external_reference_id = models.CharField(null=True) # ID in Esturdi
```

## 5. Open Questions

1.  **Tie-Breaking**: The current `vmlc` utils don't seem to have explicit tie-breaking logic other than database sort order. `competition` needs a clear rule (e.g., "Submission Time" or "Shared Rank").
2.  **Facilitator ID**: If an exam is run on Esturdi, does a `vmlc.Exam` record exist?
    *   *Assumption*: No. `Standings` might point to `exam=None` and use `external_reference_id`, OR we create a "stub" Exam in `vmlc`.
    *   *Recommendation*: Make `Standings.exam` nullable to support external engines.

