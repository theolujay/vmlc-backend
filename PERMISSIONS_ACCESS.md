# Candidate Journey & Competition-Aware Permissions: Implementation Report

This document outlines the improvements made to the candidate journey, automation, and permissions within the VMLC backend.

## 1. Accomplished: Automated Candidate Journey

### A. Automatic Enrollment during Registration
**Location**: `vmlc/v2/serializers/registration.py`

Candidates are now automatically enrolled in the `ACTIVE` competition upon registration. 
- A `CandidateCompetition` record is created (the existence of this record implies enrollment).
- The candidate is placed in the first available `Stage` (usually Screening).
- A `CandidateStageProgress` record is initialized as `IN_PROGRESS`.

### B. Competition Context Middleware
**Location**: `identity/middleware.py`

The `CompetitionContextMiddleware` has been implemented and registered in `config/settings/base.py`. 
- It attaches `request.participation` (the candidate's active `CandidateCompetition` record) to every request.
- This eliminates redundant database queries in views and permission classes.

### C. Competition-Aware Permissions
**Location**: `identity/permissions.py` and `vmlc/permissions.py`

Permissions have been refactored to use the dynamic `request.participation` context:
- `IsInStage('stage_type')`: Grants access based on the candidate's `current_stage` in the active competition.
- `IsActiveCompetitionParticipant`: Ensures the candidate's participation status is `ACTIVE`.
- Static `role` fields (like `Candidate.role`) are now secondary to the dynamic competition state.

### D. Manual/Triggered Progression (Staff Control)
**Location**: `competition/services/progression.py` & `competition/views.py`

A `ProgressionService` and `PromoteCandidatesView` have been implemented to allow staff to move candidates between stages:
- **Promotion Source**: Based on Screening `Standings` or League `AggregateLeaderboard`.
- **Cutoff**: Uses a `cutoff_rank` (e.g., top 100) provided in the request or from stage configuration.
- **Side Effects**: Automatically marks previous stage as `COMPLETED`, initializes the new stage as `IN_PROGRESS`, and eliminates candidates who fall below the cutoff.

---

## 2. Updated Candidate Journey Overview

1.  **Registration**: `RegistrationV2View` -> Creates `User`, `Candidate`, and **auto-enrolls** in `Competition`.
2.  **Screening**: Candidate takes Screening exams. Staff publishes standings.
3.  **Promotion (Staff Action)**: Staff calls `/api/v1/competition/promote/` with `from_stage="screening", to_stage="league", cutoff_rank=100`.
4.  **League**: Candidate's `current_stage` is now `league`. Their API access to league resources is **automatically unlocked** via `IsInStage('league')`.
5.  **Final**: Process repeats for the Final stage.

---



## 3. Next Steps & Recommendations



1.  **Migration Script**: [COMPLETED] Created `enroll_candidates` management command to enroll existing candidates into the active competition.

2.  **UI Integration**: The "Promote Candidates" action should be exposed in the Staff Dashboard UI, perhaps with a "Simulate Promotion" feature to see who would make the cut before finalizing.

3.  **Automated Promotion Policy**: Consider adding a "Finalize and Promote" checkbox to the `PublishStandingsView` to combine these steps for the final round of a stage.

4.  **Notification**: [COMPLETED] Candidates now receive platform notifications when they are promoted or eliminated via `ProgressionService`.