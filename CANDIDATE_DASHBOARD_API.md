# Candidate Dashboard API Documentation

The Candidate Dashboard endpoint provides a comprehensive view of a candidate's status, active exams, performance metrics, and history within the competition.

**Endpoint:** `GET /candidate/dashboard/`
**Authentication:** Required (Candidate token)
**Permissions:** Candidate Profile Required

---

## Response Schema

The response is a JSON object containing four primary sections:

1.  [`enrollment_stage_progress`](#1-enrollment-stage-progress): Current stage placement and advancement history.
2.  [`active_exam`](#2-active-exam): Details about the currently active or upcoming examination.
3.  [`performance`](#3-performance): Unified performance context including active stage metadata and ranking history.
4.  [`exam_history`](#4-exam-history): A chronological list of all previous exam attempts and results.

---

### 1. Enrollment Stage Progress
Tracks the candidate's journey through the competition stages.

| Field | Type | Description |
| :--- | :--- | :--- |
| `current_stage` | `string` | The slug of the current stage (e.g., `"screening"`, `"league"`, `"final"`). |
| `current_round` | `integer` | The latest round number active in the current stage. |
| `total_rounds` | `integer` | Total number of rounds configured for the current stage. |
| `published_rounds` | `integer` | Number of rounds in the current stage that have published results. |
| `has_taken_current_round` | `boolean` | Whether the candidate has submitted an attempt for the current round. |
| `qualification_status` | `object` | Current standing regarding promotion/active status. |
| `history` | `array` | List of stage progress records (started, completed, etc.). |

---

### 2. Active Exam
Details for the primary action item (Ongoing or Scheduled exam).

| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | `uuid` | Unique identifier for the exam. |
| `title` | `string` | Display title of the exam. |
| `status` | `string` | Current status: `"scheduled"`, `"ongoing"`, `"concluded"`, `"awaiting_results"`, `"results_published"`. |
| `stage` | `string` | Stage this exam belongs to. |
| `round` | `integer` | Round number within the stage. |
| `starts_at` | `iso8601` | When the exam window opens. |
| `ends_at` | `iso8601` | When the exam window closes. |
| `duration_minutes` | `integer` | Total time allowed for the exam once started. |
| `attempt` | `object` | Details of the candidate's interaction (`started_at`, `submitted_at`, `deadline`). |

---

### 3. Performance
The core of the dashboard's "Performance" component. It provides both the data and the metadata required for rich UI rendering.

#### `active_context`
This object provides a pre-computed "Performance Context" for the candidate's current stage.

| Field | Type | Description |
| :--- | :--- | :--- |
| `stage` | `string` | Current stage slug. |
| `stage_display` | `string` | Human-readable label (e.g., `"League Stage"`). |
| `title` | `string` | Dynamic title (e.g., `"League Performance • Round 3 of 6"`). |
| `accent_color` | `string` | Hex code for stage-specific branding. |
| `ranking` | `object` | Current ranking data (`position`, `total_candidates`, `score`, `rank_change`). |
| `scoreboards` | `array` | List of available ranking/leaderboard links (e.g., `[{ "label": "League Leaderboard", "type": "leaderboard", "stage": "League", "is_current": true }]`). For `type: "ranking"`, `exam_id` is required. |
| `status_meta` | `object` | Metadata for the status banner (see below). |

#### `status_meta`
Drives the interactive status banner and qualification messaging.

| Field | Type | Description |
| :--- | :--- | :--- |
| `status_type` | `string` | Semantic state: `"success"`, `"pending"`, `"info"`, `"warning"`, `"error"`, `"eliminated"`, `"disqualified"`. |
| `status_label` | `string` | Heading for the status banner (e.g., `"On Track for the Finals"`, `"Results on the Way"`, `"Screening Upcoming"`). |
| `status_subtext` | `string` | Context-aware explanatory text (e.g., `"The screening hasn't started yet. We'll notify you when it does."`). |
| `color` | `string` | Text/Icon hex color. |
| `bg_color` | `string` | Background hex color. |
| `icon` | `string` | Icon name (e.g., `"check"`, `"clock"`, `"info"`, `"calendar"`, `"alert"`). |
| `metric_label` | `string` | Label for the qualification threshold. |
| `metric_value_display` | `string` | Human-readable threshold value (e.g., `"Top 100"`). |

---

### 4. Exam History
A list of all previous exam results.

| Field | Type | Description |
| :--- | :--- | :--- |
| `exam_id` | `uuid` | Exam ID. |
| `exam_title` | `string` | Title. |
| `score` | `float` | Truncated score (only visible if `is_published` is true). |
| `percentage` | `float` | Score percentage (same as score for now). |
| `status` | `string` | Final state of the exam. |
| `is_published` | `boolean` | Whether results are officially released. |

---

## Example Response

```json
{
  "enrollment_stage_progress": {
    "current_stage": "league",
    "current_round": 3,
    "total_rounds": 6,
    "published_rounds": 2,
    "has_taken_current_round": true,
    "qualification_status": {
      "is_qualified": true,
      "advancement_policy": { "mode": "top_n", "value": 100 },
      "message": "You are currently Active in the League stage."
    }
  },
  "active_exam": {
    "id": "...",
    "title": "League Round 3",
    "status": "awaiting_results",
    "attempt": {
      "submitted_at": "2026-03-05T14:30:00Z"
    }
  },
  "performance": {
    "active_context": {
      "stage": "league",
      "stage_display": "League Stage",
      "title": "League Performance • Round 2 of 6",
      "accent_color": "#3E4095",
      "ranking": {
        "position": 42,
        "total_candidates": 1200,
        "score": 185.5,
        "rank_change": 5,
        "is_active": true
      },
      "scoreboards": [
        {
          "label": "League Leaderboard",
          "type": "leaderboard",
          "stage": "League",
          "is_current": true
        },
        {
          "label": "Screening Ranking",
          "type": "ranking",
          "exam_id": "screening-exam-id",
          "stage": "Screening",
          "is_current": false
        }
      ],
      "status_meta": {
        "status_type": "success",
        "status_label": "On Track for the Finals",
        "status_subtext": "You're within the qualification range. Keep it up.",
        "color": "#018ABB",
        "bg_color": "#CCEEFB33",
        "icon": "check",
        "metric_label": "Finalist Qualification Cut-off",
        "metric_value_display": "Top 100"
      }
    },
    "history": [
      {
        "stage": "screening",
        "ranking": { "position": 10, "score": 98.0 }
      }
    ]
  },
  "exam_history": [...]
}
```
