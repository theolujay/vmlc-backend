# CACHING_STRATEGY.md: VMLC Caching & Invalidation Logic

This document defines the strategy for managing cache consistency across the VMLC backend, ensuring candidates and staff see up-to-date information without overloading the database.

## 1. Problem Statement
Active competitions generate frequent data updates (exam submissions, standings, promotions). Using a static TTL (e.g., 24 hours) causes "Stale Data Drift" where a candidate might be promoted in the DB but see a "Screening" dashboard for hours.

## 2. Key Cache Groups

| Group | Scope | Key Pattern | Main Dependency |
| :--- | :--- | :--- | :--- |
| **Candidate Dashboard** | Per User | `dash:cand:{uuid}` | `CandidateCompetition`, `Notification`, `ExamResult` |
| **Staff Dashboard** | Global | `dash:staff:global` | All `CandidateCompetition`, `Exam` statuses |
| **Leaderboards** | Per Stage | `lb:{stage}:{round}` | `Standings`, `AggregateLeaderboard` |
| **Participation** | Per User | `part:{user_id}` | `CandidateCompetition` |

---

## 3. Invalidation Strategy: "Event-Driven Clearing"

Instead of relying solely on TTL, we will implement **Signal-based Invalidation**.

### A. Candidate-Level Invalidation
Whenever a candidate's state changes, their specific dashboard and participation cache must be cleared.

**Triggering Events:**
- Candidate profile update.
- Exam submission.
- Receipt of a new Notification.
- Status change (Withdrawal/Disqualification).

**Implementation:**
```python
# Create a utility in vmlc/v2/utils.py
def invalidate_candidate_cache(candidate_id, user_id=None):
    keys = [f"dash:cand:{candidate_id}", f"candidate_dashboard_v2_{candidate_id}"]
    if user_id:
        keys.append(f"part:{user_id}")
    delete_many_cache(keys)
```

### B. Competition-Level Invalidation (Batch)
When standings are published or candidates are promoted, large groups of users are affected.

**Triggering Events:**
- Standings published (Clears all dashboards for that stage).
- Progression Service triggers Promotion (Clears all dashboards for the competition).
- Staff Dashboard stats change.

**Implementation Logic:**
- If 100 candidates are promoted, clear their individual caches via a background task to prevent request blocking.
- Clear `dash:staff:global` whenever `CandidateCompetition` is saved or deleted.

---

## 4. Middleware & Context Caching

The `CompetitionContextMiddleware` currently queries the DB on every request. We should optimize this using a short-lived cache.

```python
# identity/middleware.py optimization
def process_request(self, request):
    if request.user.is_authenticated and hasattr(request.user, 'candidate_profile'):
        cache_key = f"part:{request.user.id}"
        request.participation = get_or_set_cache(
            cache_key, 
            lambda: EligibilityService.get_active_participation(request.user.candidate_profile),
            ttl=300 # 5-minute cache for context
        )
```

---

## 5. Implementation Roadmap

1.  **Refactor Key Naming**: Move away from ad-hoc strings to a centralized `CacheKeys` helper class to avoid typos.
2.  **Centralized Invalidation Service**: Create `vmlc/services/cache_service.py` to handle logic like "clear all league candidate caches".
3.  **Hooks in Services**:
    - `ProgressionService.promote_candidates`: Call invalidation at the end of the transaction.
    - `StandingsGenerator`: Invalidate relevant leaderboards upon publication.
4.  **Django Signals**:
    - `post_save` on `Notification`: Clear the recipient's dashboard cache.
    - `post_save` on `CandidateExamResult`: Clear the candidate's dashboard cache.

## 6. Summary of TTL Defaults
- **Dashboards**: 1 Hour (but cleared immediately on change).
- **Participation Context**: 5 Minutes.
- **Leaderboards**: 24 Hours (but cleared immediately on Standings publication).
- **Static Config**: 24 Hours.
