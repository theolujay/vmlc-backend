# Candidate Ranking Detail API

This endpoint provides comprehensive performance and identity data for a specific candidate within a specific exam ranking snapshot.

## Endpoint

**Path:** `/competition/rankings/<uuid:exam_id>/candidate/<uuid:candidate_id>/`
**Method:** `GET`
**Authentication:** Required (Staff or the Candidate themselves)

## Response Structure

The response is a JSON object containing three main sections: `exam_details`, `candidate_info`, and `candidate_performance`.

### 1. `exam_details`
High-level information about the exam and overall performance metrics for the ranking snapshot.

| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | UUID | Unique identifier for the exam. |
| `title` | String | Display title of the exam (e.g., "Screening Test", "League Round 1"). |
| `stage` | String | Competition stage (`screening`, `league`, `final`). |
| `round` | Integer \| null | Round number within the stage (relevant for League). |
| `scheduled_date` | DateTime \| null | When the exam was scheduled to start. |
| `concluded_at` | DateTime \| null | When the exam officially ended. |
| `total_questions` | Integer | Total number of questions in the exam. |
| `total_candidates` | Integer | Total number of eligible candidates in this ranking snapshot. |
| `average_score` | Float | Average score achieved by all participants in this exam. |

### 2. `candidate_info`
Identity and institutional details of the candidate.

| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | UUID | Unique identifier for the candidate. |
| `full_name` | String | Full name of the candidate. |
| `email` | String | Email address of the candidate. |
| `state` | String | State of residence/origin of the candidate. |
| `school_name` | String | Name of the candidate's school. |
| `school_type` | String | Type of school (`public`, `private`). |
| `current_class` | String | Class in school (`SS1`, `SS2`, `SS3`). |

### 3. `candidate_performance`
Detailed breakdown of the candidate's execution and results.

| Field | Type | Description |
| :--- | :--- | :--- |
| `score` | Float \| "absent" | The candidate's final score. Returns `"absent"` if no attempt was found. |
| `rank` | Integer | The candidate's rank in this specific ranking snapshot. |
| `percentile` | Float \| null | The candidate's percentile score. |
| `recorded_at` | DateTime \| null | When the exam result was recorded. |
| `auto_score` | Boolean | Whether the score was automatically computed by the system. |
| `started_at` | DateTime \| null | Time the candidate started the exam session (from `ExamAccess`). |
| `submitted_at` | DateTime \| null | Time the candidate submitted the exam (from `ExamAccess`). Used as the primary tie-break factor. |
| `face_capture` | URL \| null | Absolute URL to the face capture image taken during the exam. |
| `submissions` | Array | List of individual question responses (only if result exists). |

#### `submissions` Array Item:
| Field | Type | Description |
| :--- | :--- | :--- |
| `question` | Object | Full question object including text, options, and correct answer. |
| `selected_option` | String \| null | The option selected by the candidate (`A`, `B`, `C`, `D`, or `null`). |
| `answered_at` | DateTime | Timestamp of the response. |

---

## Example Response (Standard Result)

```json
{
    "exam_details": {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "title": "League Round 1",
        "stage": "league",
        "round": 1,
        "scheduled_date": "2026-03-01T09:00:00Z",
        "concluded_at": "2026-03-01T10:00:00Z",
        "total_questions": 50,
        "total_candidates": 120,
        "average_score": 34.5
    },
    "candidate_info": {
        "id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
        "full_name": "Jane Doe",
        "email": "jane.doe@example.com",
        "state": "Lagos",
        "school_name": "Example International School",
        "school_type": "private",
        "current_class": "SS1"
    },
    "candidate_performance": {
        "score": 45.0,
        "rank": 3,
        "percentile": 97.5,
        "recorded_at": "2026-03-01T09:45:00Z",
        "auto_score": true,
        "started_at": "2026-03-01T09:05:00Z",
        "submitted_at": "2026-03-01T09:44:55Z",
        "face_capture": "https://api.vmlc.edu/media/exam_face_captures/face_6ba7.jpg",
        "submissions": [
            {
                "question": {
                    "id": 101,
                    "text": "What is 2 + 2?",
                    "option_a": "3",
                    "option_b": "4",
                    "option_c": "5",
                    "option_d": "6",
                    "correct_answer": "B",
                    "difficulty": "easy"
                },
                "selected_option": "B",
                "answered_at": "2026-03-01T09:06:12Z"
            }
        ]
    }
}
```

## Example Response (Absentee)

```json
{
    "exam_details": { ... },
    "candidate_info": {
        "id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
        "full_name": "John Smith",
        "email": "john.smith@example.com",
        "state": "Kano",
        "school_name": "Government College",
        "school_type": "public",
        "current_class": "SS1"
    },
    "candidate_performance": {
        "score": "absent",
        "rank": 115,
        "percentile": 4.16,
        "recorded_at": null,
        "auto_score": false,
        "started_at": null,
        "submitted_at": null,
        "face_capture": null,
        "submissions": []
    }
}
```
