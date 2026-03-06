# Staff Competition Dashboard API Documentation

The Staff Competition Dashboard endpoint provides an aggregated view of competition statistics, candidate progress through the funnel, exam participation metrics, and top performers.

**Endpoint:** `GET /competition/dashboard/staff`  
**Authentication:** Required (Staff token)  
**Permissions:** Active Volunteer Profile Required

---

## Response Schema

The response is a JSON object containing five primary sections:

1.  [`stats`](#1-global-stats): Global enrollment numbers and stage-wise participation funnel.
2.  [`progress`](#2-stage-progress): Current stage and round context for the active competition.
3.  [`exams`](#3-exams-list): Detailed participation and performance metrics for all exams in the competition.
4.  [`leaderboard_summary`](#4-leaderboard-summary): Top 3 candidates in the current cumulative league leaderboard.
5.  [`latest_ranking_summary`](#5-latest-ranking-summary): Top 3 performers from the most recently published ranking snapshot.

---

### 1. Global Stats
High-level overview of the candidate pool and its distribution.

| Field | Type | Description |
| :--- | :--- | :--- |
| `enrolled` | `integer` | Total number of candidates ever enrolled in this edition. |
| `active` | `integer` | Candidates currently eligible and participating. |
| `eliminated` | `integer` | Candidates removed via competition promotion rules. |
| `disqualified` | `integer` | Candidates removed due to violations or inactive accounts. |
| `stage_breakdown` | `object` | Map of stage slugs to the count of active candidates currently in that stage. |

---

### 2. Stage Progress
Metadata about the competition's current operational state.

| Field | Type | Description |
| :--- | :--- | :--- |
| `current_stage` | `string` | Slug of the most recently active stage. |
| `current_round` | `integer` | The latest round number currently being assessed. |
| `total_rounds` | `integer` | Total rounds configured for the current stage. |
| `published_rounds` | `integer` | Number of rounds in the current stage with officially released results. |

---

### 3. Exams List
A detailed list of all exams (Screening, League, Final) with batch-computed analytics.

| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | `uuid` | Exam ID. |
| `title` | `string` | Display name of the exam. |
| `stage` | `string` | Stage slug. |
| `round` | `integer` | Round number (if applicable). |
| `status` | `string` | Current exam state (`"scheduled"`, `"ongoing"`, `"concluded"`). |
| `ranking_status` | `string` | Results state: `"pending"` (no snapshot), `"ready"` (draft snapshot), `"published"` (public). |
| `stats` | `object` | Performance metrics (see below). |

#### `stats` (Exam-specific)
| Field | Type | Description |
| :--- | :--- | :--- |
| `candidates_sat` | `integer` | Number of candidates who submitted an attempt. |
| `eligible_candidates` | `integer` | Approximation of total candidates eligible for this stage. |
| `participation_rate` | `float` | Percentage of eligible candidates who participated. |
| `avg_score` | `float` | Mean score of all participants. |
| `highest_score` | `float` | Highest score achieved in the exam. |
| `lowest_score` | `float` | Lowest score achieved in the exam. |

---

### 4. Leaderboard Summary
The Top 3 candidates from the cumulative League Leaderboard.

| Field | Type | Description |
| :--- | :--- | :--- |
| `entries` | `array` | List of Top 3 entries including `candidate_name`, `total_score`, and `overall_rank`. |

---

### 5. Latest Ranking Summary
Focus on the most recently published single-exam ranking.

| Field | Type | Description |
| :--- | :--- | :--- |
| `exam_id` | `uuid` | Exam ID. |
| `exam_title` | `string` | Exam Title. |
| `stage` | `string` | Stage slug. |
| `round` | `integer` | Round number. |
| `entries` | `array` | List of Top 3 performers in this specific exam. |

---

## Example Response

```json
{
  "stats": {
    "enrolled": 1500,
    "active": 1200,
    "eliminated": 250,
    "disqualified": 50,
    "stage_breakdown": {
      "screening": 0,
      "league": 1200,
      "final": 0
    }
  },
  "progress": {
    "current_stage": "league",
    "current_round": 3,
    "total_rounds": 6,
    "published_rounds": 2
  },
  "exams": [
    {
      "id": "...",
      "title": "League Round 3",
      "stage": "league",
      "round": 3,
      "status": "concluded",
      "ranking_status": "ready",
      "stats": {
        "candidates_sat": 1150,
        "eligible_candidates": 1200,
        "participation_rate": 95.83,
        "avg_score": 72.4,
        "highest_score": 100.0,
        "lowest_score": 12.5
      }
    }
  ],
  "leaderboard_summary": [
    { "full_name": "Alice Johnson", "total_score": 285.5, "overall_rank": 1 },
    { "full_name": "Bob Smith", "total_score": 279.0, "overall_rank": 2 },
    { "full_name": "Charlie Davis", "total_score": 275.2, "overall_rank": 3 }
  ],
  "latest_ranking_summary": {
    "exam_title": "League Round 2",
    "stage": "league",
    "round": 2,
    "entries": [...]
  }
}
```
