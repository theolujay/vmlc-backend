# Optimization Proposal: Candidate Records & Access Control

This document outlines the strategy to decouple candidate logic from the `identity` models, centralize computation in `vmlc`, and implement robust, model-driven access control using the `competition` architecture.

## 1. Problem Statement

Currently, the `Candidate` model in `identity/models.py` contains significant business logic (`get_records`, `_get_available_exams`, `_get_performance_stats`). This design presents several issues:

1.  **Tight Coupling**: Identity models should focus on authentication and profile data, not business rules or exam availability logic.
2.  **Brittle Permissions**: Logic relies on the `candidate.role` string (e.g., `stage=self.role`) to determine access. This ignores the dynamic nature of competitions (e.g., specific editions, active enrollment status, disqualifications).
3.  **Legacy Dependencies**: Performance stats rely on `CandidateExamResultSnapshot`, which is less real-time and granular than the new `RankingSnapshot` and `Leaderboard` architecture.

## 2. Proposed Architecture

We will refactor this logic into a dedicated service layer, likely located in `vmlc/services/candidate_records.py`. This service will bridge the gap between `identity` (who is the user?), `competition` (what is their context?), and `vmlc` (what content can they access?).

### 2.1. Decoupled Service Layer

A new class, `CandidateRecordService`, will handle all computations.

```python
# vmlc/services/candidate_records.py

class CandidateRecordService:
    """
    Handles retrieval of candidate performance history, available exams,
    and profile status by leveraging Competition context.
    """
    @staticmethod
    def get_available_exams(candidate: Candidate) -> List[Dict]:
        ...

    @staticmethod
    def get_performance_history(candidate: Candidate) -> Dict:
        ...
```

## 3. Enhanced Access Control & Logic

Instead of checking `if candidate.role == 'league'`, we will leverage the relational depth of `competition/models.py`.

### 3.1. Determining Available Exams

**Current Logic (Legacy):**
```python
# identity/models.py
Exam.objects.filter(stage=self.role, is_active=True)
```

**Proposed Logic (Optimized):**
The availability of an exam should be determined by the candidate's **active enrollment** in a **current stage** of an **active competition**.

1.  **Fetch Context**: Query `CandidateCompetition` to find the active enrollment for the candidate.
    *   *Check*: `competition.status == ACTIVE`
    *   *Check*: `participant.status == ACTIVE` (Handles disqualification/elimination automatically).
2.  **Identify Stage**: Use `participant.current_stage`.
3.  **Fetch Exams**: Query `StageExam` (the bridge model) to find exams linked to this specific stage.
4.  **Verify Exam Window**: Check `Exam.is_currently_open`.

**Pseudocode Implementation:**
```python
def get_available_exams(candidate):
    # 1. Get active context
    enrollment = CandidateCompetition.objects.filter(
        candidate=candidate,
        competition__status=Competition.Status.ACTIVE,
        status=CandidateCompetition.Status.ACTIVE
    ).select_related('current_stage').first()

    if not enrollment or not enrollment.current_stage:
        return []

    # 2. Get exams for this specific stage
    # This decouples the 'Exam' definition from the 'Stage' execution
    stage_exams = StageExam.objects.filter(
        competition_stage=enrollment.current_stage,
        is_active=True
    ).select_related('exam')

    available = []
    for slot in stage_exams:
        exam = slot.exam
        # 3. Check time windows
        if exam.is_active and exam.is_currently_open:
            # 4. Check if already taken (optional, depending on retake policy)
            if not has_taken_exam(candidate, exam):
                available.append(serialize_exam(exam, slot))
    
    return available
```

### 3.2. Performance History

**Current Logic (Legacy):**
Aggregates `CandidateExamResult` and uses `CandidateExamResultSnapshot` for ranking.

**Proposed Logic (Optimized):**
1.  **History**: Query `CandidateExamResult` but join with `competition.StageExam` to infer which stage/round the exam belonged to at the time.
2.  **Ranking**: 
    *   For **League**: Delegate to `competition.services.LeaderboardService` to fetch the `AggregateLeaderboardEntry`.
    *   For **Screening/Final**: Query `competition.StandingsEntry` for specific exam snapshots.

## 4. Benefits

1.  **Granular Control**: A candidate can be in the "League" role but effectively "Eliminated" in the `CandidateCompetition` model. The new logic respects this immediately (no available exams) without changing the user's global role.
2.  **Separation of Concerns**: `identity` models remain lightweight. `vmlc` handles content. `competition` handles rules.
3.  **Scalability**: We can run multiple competitions or test-runs simultaneously. The legacy logic (`stage=candidate.role`) assumes a single global context. The new logic finds the *specific* active competition context.

## 5. Migration Steps

1.  **Create Service**: Implement `vmlc/services/candidate_records.py`.
2.  **Refactor Views**: Update `ExamHistoryView`, `CandidateMeView`, and `CandidateDashboardView` (if applicable) to consume this service.
3.  **Cleanup**: Remove the deprecated methods (`get_records`, etc.) from `identity/models.py`.
