# Exam API Endpoints Documentation

This document outlines the API endpoints related to exams, prioritizing V2 over V1 where available.

## Base URLs
- V1: `/v1/`
- V2: `/v2/`
- Competition: `/v1/competition/`

---

## 1. List Exams
**Endpoint:** `GET /v2/exams/`  
**Description:** Returns a list of all exams with basic metadata.  
**Permissions:** `ActiveAdminPermissions` (Staff only)

### Response Body
```json
{
  "count": 100,
  "next": "http://api.vmlc.com/v2/exams/?page=2",
  "previous": null,
  "question_pool_data": {
    "total_questions": 500,
    "hard_questions_count": 100,
    "moderate_questions_count": 250,
    "easy_questions_count": 150
  },
  "results": [
    {
      "id": "uuid",
      "title": "League Round 1",
      "status": "scheduled",
      "competition_edition": 3,
      "competition_title": "Verboheit MLC 3.0",
      "stage": "league",
      "stage_display": "League",
      "question_count": 50,
      "scheduled_date": "2024-05-01T10:00:00Z",
      "concluded_at": "2024-05-01T22:00:00Z",
      "created_at": "2024-04-01T12:00:00Z",
      "standings": {
        "exists": true,
        "is_published": false,
        "created_at": "2024-05-02T08:00:00Z",
        "published_at": null
      }
    }
  ]
}
```

---

## 2. Create Exam
**Endpoint:** `POST /v2/exams/`  
**Description:** Creates a new exam.  
**Permissions:** `ActiveAdminPermissions` (Staff only)

### Request Body
| Field | Type | Description |
| :--- | :--- | :--- |
| `description` | String | **Optional.** Detailed description of the exam. |
| `open_duration_hours` | Integer | **Optional.** (Default: 12) Duration the exam window stays open. |
| `countdown_minutes` | Integer | **Optional.** (Default: 60) Time limit once a candidate starts. |
| `scheduled_date` | String (ISO) | **Optional.** When the exam window begins. |
| `is_active` | Boolean | **Optional.** (Default: true) Whether the exam is active. |
| `stage_id` | Integer | **Optional.** ID of the competition stage to link to. |
| `round` | Integer | **Optional.** Round number (required for League stages). |
| `questions` | Array (UUID) | **Optional.** List of question IDs to include. |

```json
{
  "description": "Optional description",
  "open_duration_hours": 12,
  "countdown_minutes": 60,
  "scheduled_date": "2024-05-01T10:00:00Z",
  "is_active": true,
  "stage_id": 1, 
  "round": 1,
  "questions": ["uuid1", "uuid2"]
}
```

### Response Body
Returns the full exam object (see **Get Exam Details**).

---

## 3. Get Exam Details
**Endpoint:** `GET /v2/exams/{exam_id}/`  
**Description:** Retrieves detailed information about a single exam, including paginated questions.  
**Permissions:** `ActiveAdminPermissions` (Staff only)

### Response Body
```json
{
  "id": "uuid",
  "title": "League Round 1",
  "description": "Detailed description",
  "status": "scheduled",
  "is_active": true,
  "is_currently_open": false,
  "competition_edition": 2024,
  "competition_name": "VMLC 2024",
  "stage": "league",
  "stage_display": "League",
  "open_duration_hours": 12,
  "countdown_minutes": 60,
  "scheduled_date": "2024-05-01T10:00:00Z",
  "concluded_at": "2024-05-01T22:00:00Z",
  "created_at": "2024-04-01T12:00:00Z",
  "created_by": { "id": "uuid", "full_name": "Staff Name", "email": "staff@vmlc.com" },
  "updated_by": null,
  "standings": {
    "exists": true,
    "is_published": false,
    "created_at": "2024-05-02T08:00:00Z",
    "published_at": null
  },
  "questions": {
    "question_pool_data": { ... },
    "results": [
      {
        "id": 1,
        "text": "What is 2+2?",
        "difficulty": "easy",
        "created_at": "..."
      }
    ],
    "count": 50,
    "next": null,
    "previous": null
  }
}
```

---

## 4. Update Exam
**Endpoint:** `PUT/PATCH /v2/exams/{exam_id}/`  
**Description:** Updates an existing exam. Cannot update if exam is ongoing, concluded, or cancelled.  
**Permissions:** `ActiveAdminPermissions` (Staff only)

### Request Body
Fields same as **Create Exam** (all optional for PATCH).

---

## 5. Delete Exam
**Endpoint:** `DELETE /v2/exams/{exam_id}/`  
**Description:** Removes an exam instance.  
**Permissions:** `ActiveAdminPermissions` (Staff only)

---

## 6. List Exam Questions
**Endpoint:** `GET /v2/exams/{exam_id}/questions/`  
**Description:** Returns all questions belonging to an exam.  
**Permissions:** `ActiveAdminPermissions` (Staff only)

### Response Body
```json
[
  {
    "id": 1,
    "text": "Question text",
    "option_a": "...",
    "option_b": "...",
    "option_c": "...",
    "option_d": "...",
    "correct_answer": "A",
    "difficulty": "moderate",
    "created_at": "..."
  }
]
```

---

## 7. List Exam Results
**Endpoint:** `GET /v2/exams/{exam_id}/results/`  
**Description:** Returns candidate results for a specific exam, ordered by score descending.  
**Permissions:** `ActiveAdminPermissions` (Staff only)

### Response Body
```json
[
  {
    "candidate_name": "John Doe",
    "candidate_school_name": "VMLC Academy",
    "score": 85.50,
    "auto_score": true,
    "score_submitted_by": null,
    "recorded_at": "2024-05-01T15:00:00Z"
  }
]
```

---

## 8. Take Exam (Start Exam)
**Endpoint:** `GET /v2/exams/{exam_id}/take-exam/`  
**Description:** Returns exam details and questions for a candidate to begin the assessment. Verifies candidate eligibility.  
**Permissions:** `CandidatePermissions`

### Response Body
```json
{
  "id": "uuid",
  "title": "League Round 1",
  "description": "...",
  "open_duration_hours": 12,
  "scheduled_date": "...",
  "countdown_minutes": 60,
  "questions": [
    {
      "id": 1,
      "text": "...",
      "option_a": "...",
      "option_b": "...",
      "option_c": "...",
      "option_d": "..."
    }
  ]
}
```

---

## 9. Submit Exam Answers
**Endpoint:** `POST /v1/exams/{exam_id}/submit-exam-answers/`  
**Description:** Submits a candidate's answers for an exam. Prevents re-submission and validates exam window.  
**Permissions:** `CandidatePermissions`

### Request Body
| Field | Type | Description |
| :--- | :--- | :--- |
| `answers` | Array | **Required.** List of question answers. |
| `answers[].question` | Integer | **Required.** ID of the question. |
| `answers[].selected_option` | String | **Optional.** The chosen option (A, B, C, D). Empty string if unanswered. |

```json
{
  "answers": [
    {
      "question": 1,
      "selected_option": "A"
    },
    {
      "question": 2,
      "selected_option": ""
    }
  ]
}
```

### Response Body
```json
{
  "message": "Answers submitted successfully!"
}
```

---

## 10. Candidate Exam History
**Endpoint:** `GET /v2/candidates/{candidate_id}/exam-history/`  
**Description:** Retrieves the list of exams taken by a specific candidate and their outcomes.  
**Permissions:** `ActiveAdminPermissions` OR the candidate themselves.

### Response Body
```json
[
  {
    "exam_id": "uuid",
    "exam_title": "Screening 2024",
    "score": 70.00,
    "status": "completed",
    "recorded_at": "..."
  }
]
```

---

## 11. Bulk Add Questions to Exams
**Endpoint:** `POST /v1/questions/bulk-add-to-exams/`  
**Description:** Add multiple questions to multiple exams in one operation.  
**Permissions:** `ActiveAdminPermissions` (Staff only)

### Request Body
| Field | Type | Description |
| :--- | :--- | :--- |
| `question_ids` | Array (Integer) | **Required.** List of question IDs. |
| `exam_ids` | Array (UUID) | **Required.** List of exam IDs. |

```json
{
    "question_ids": [1, 2, 3],
    "exam_ids": ["uuid-exam-1", "uuid-exam-2"]
}
```

### Response Body
```json
{
    "summary": {
        "total_operations": 6,
        "successful": 6,
        "skipped": 0,
        "failed": 0
    },
    "details": { ... }
}
```

---

## 12. Question-Exam Association
**Endpoint:** `POST /v1/questions/{question_id}/exams/`  
**Description:** Add or remove a single question from multiple exams.  
**Permissions:** `ActiveAdminPermissions` (Staff only)

### Request Body
| Field | Type | Description |
| :--- | :--- | :--- |
| `add_to_exams` | Array (UUID) | **Optional.** Exam IDs to add this question to. |
| `remove_from_exams` | Array (UUID) | **Optional.** Exam IDs to remove this question from. |

```json
{
    "add_to_exams": ["uuid-exam-1"],
    "remove_from_exams": ["uuid-exam-2"]
}
```

### Response Body
```json
{
    "added": [ { "exam_id": "...", "exam_title": "..." } ],
    "removed": [ { "exam_id": "...", "exam_title": "..." } ],
    "failed_additions": [],
    "failed_removals": []
}
```

---

## 13. Publish Standings
**Endpoint:** `POST /v1/competition/standings/publish/`  
**Description:** Triggers the generation and optional immediate publishing of standings for an exam.  
**Permissions:** `ActiveAdminPermissions` (Staff only)

### Request Body
| Field | Type | Description |
| :--- | :--- | :--- |
| `exam_id` | UUID | **Required.** UUID of the Exam to generate standings for. |
| `publish_now` | Boolean | **Optional.** (Default: false) If true, immediately marks standings as published. |

```json
{
    "exam_id": "uuid-exam-1",
    "publish_now": true
}
```

### Response Body
```json
{
    "message": "Standings generation has been started."
}
```

---

## 14. Retrieve Standings
**Endpoint:** `GET /v1/competition/standings/{exam_id}/`  
**Description:** Retrieves the full standings for a specific exam, including all candidate entries.  
**Permissions:** `ActiveAdminPermissions` (Staff only)

### Response Body
```json
{
    "id": 1,
    "competition": 1,
    "stage": "league",
    "stage_display": "League",
    "round": 1,
    "exam": "uuid-exam-1",
    "facilitator_system": "vmlc",
    "is_published": true,
    "published_at": "...",
    "meta": {},
    "created_at": "...",
    "entries": [
        {
            "candidate": "uuid-candidate-1",
            "candidate_name": "John Doe",
            "candidate_email": "john@example.com",
            "school_name": "Academy",
            "exam_score": 95.00,
            "rank": 1,
            "percentile": 99.0,
            "tie_break_reason": null
        }
    ]
}
```

---

## 15. Retrieve Candidate Standing Detail
**Endpoint:** `GET /v1/competition/standings/{exam_id}/candidate/{candidate_id}/`  
**Description:** Retrieves detailed performance for a specific candidate in a specific exam standing.  
**Permissions:** `ActiveAdminPermissions` (Staff only)

### Response Body
```json
{
    "exam_details": {
        "id": "uuid-exam-1",
        "title": "League Round 1",
        "stage": "league",
        "round": 1,
        "scheduled_date": "...",
        "concluded_at": "...",
        "total_questions": 50,
        "total_candidates": 100,
        "average_score": 65.5
    },
    "candidate_performance": {
        "candidate": "uuid-candidate-1",
        "candidate_name": "John Doe",
        "candidate_email": "john@example.com",
        "school_name": "Academy",
        "score": 95.00,
        "rank": 1,
        "percentile": 99.0,
        "recorded_at": "...",
        "auto_score": true,
        "submissions": [
            {
                "question": { "id": 1, "text": "...", ... },
                "selected_option": "A",
                "answered_at": "..."
            }
        ]
    }
}
```

---

## 16. League Leaderboard
**Endpoint:** `GET /v1/competition/leaderboard/league/`  
**Description:** Retrieves the cumulative league leaderboard (Aggregate Leaderboard).  
**Permissions:** `IsLeagueParticipantOrStaff`

### Response Body
```json
{
    "id": 1,
    "competition": 1,
    "stage": "league",
    "stage_display": "League",
    "as_of_round": 3,
    "created_at": "...",
    "updated_at": "...",
    "entries": [
        {
            "candidate": "uuid-candidate-1",
            "candidate_name": "John Doe",
            "candidate_email": "john@example.com",
            "school_name": "Academy",
            "state": "Lagos",
            "total_score": 280.00,
            "overall_rank": 1,
            "rank_change": 0
        }
    ]
}
```

---

## 17. League Candidate Cumulative Detail
**Endpoint:** `GET /v1/competition/leaderboard/league/candidate/{candidate_id}/`  
**Description:** Retrieves cumulative performance for a specific candidate in the league leaderboard.  
**Permissions:** `IsLeagueParticipantOrStaff`

### Response Body
```json
{
    "candidate": "uuid-candidate-1",
    "candidate_name": "John Doe",
    "candidate_email": "john@example.com",
    "school_name": "Academy",
    "state": "Lagos",
    "total_score": 280.00,
    "overall_rank": 1,
    "rank_change": 0
}
```

---

## Frontend Client Logic & Visibility

This section describes the internal logic used to determine which exams are visible to candidates and how the dashboard behaves in edge cases.

### 1. Visibility Toggle (`StageExam.is_active`)
Visibility on the candidate dashboard is primarily controlled by the `is_active` flag on the `StageExam` (competition slot).
- **Draft State:** When an exam is created but not yet scheduled, `StageExam.is_active` is `false`. It will not appear on the dashboard.
- **Published/Scheduled State:** When an admin sets a `scheduled_date` on an exam, the system automatically flips the linked `StageExam.is_active` to `true`.
- **Deactivation:** If an exam is marked `is_active = false` on the `Exam` model, the competition slot visibility is also revoked.

### 2. Graceful Visibility (Leniency)
To prevent issues where an exam is live but the visibility flag was manually unset or missed, the **Candidate Dashboard** applies a leniency rule:
- If an exam's status is `ONGOING` (current time is within the scheduled window), it will be visible to eligible candidates **even if** `StageExam.is_active` is `false`.

### 3. Candidate Enrollment Fallback
The dashboard requires a `CandidateCompetition` record to determine a candidate's "Current Stage."
- **Enrolled Candidates:** The dashboard uses `participation.current_stage`.
- **Unenrolled Candidates:** If a candidate has no enrollment record for the active competition, the dashboard falls back to using the candidate's `role` (e.g., `screening`, `league`) to infer their current stage. This ensures that new registrants see the screening exam immediately even if the background enrollment task hasn't completed.

### 4. Awaiting Results
Once an exam is `CONCLUDED` and the candidate has participated, the exam remains visible in the "Active Exam" section with a status of `awaiting_results` until the official **Standings** are published by an admin.