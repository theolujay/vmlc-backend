# Candidate Ranking Detail API

This endpoint provides comprehensive performance and identity data for a specific candidate within a specific exam ranking snapshot.

## Endpoint

**Path:** `/competition/rankings/<uuid:exam_id>/candidate/<uuid:candidate_id>/`
**Method:** `GET`
**Authentication:** Required (Staff or the Candidate themselves)

## Response Structure

The response is a JSON object containing four main sections: `exam_details`, `candidate_info`, `candidate_performance`, and `proctoring_summary`.

### 1. `exam_details`
...
| `total_candidates` | Integer | Total number of eligible candidates in this ranking snapshot. |
| `average_score` | Float | Average score achieved by all participants in this exam. |

### 2. `candidate_info`
...
| `current_class` | String | Class in school (`SS1`, `SS2`, `SS3`). |

### 3. `candidate_performance`
Detailed breakdown of the candidate's execution and results.

| Field | Type | Description |
| :--- | :--- | :--- |
| `score` | Float \| "absent" | The candidate's final score. Returns `"absent"` if no attempt was found. |
| `rank` | Integer | The candidate's rank in this specific ranking snapshot. |
| `percentile` | Float \| null | The candidate's percentile score. |
| `time_used` | Integer \| null | Time taken to complete the exam in seconds. |
| `violation_score` | Float | Weighted average of suspicion scores from proctoring heartbeats. |
| `proctoring_status` | String \| null | One of `clear`, `suspicious`, or `flagged`. Returns `null` for absentees. |
| `tie_break_reason` | String \| null | Optional explanation when a tie-break was applied to assign the rank. |
| `recorded_at` | DateTime \| null | When the exam result was recorded. |
| `auto_score` | Boolean | Whether the score was automatically computed by the system. |
| `started_at` | DateTime \| null | Time the candidate started the exam session (from `ExamAccess`). |
| `submitted_at` | DateTime \| null | Time the candidate submitted the exam (from `ExamAccess`). Used as the primary tie-break factor. |
| `face_capture` | URL \| null | Absolute URL to the face capture image taken during the exam. |
| `submissions` | Array | List of individual question responses (only if result exists). |

### 4. `proctoring_summary`
Summary of automated proctoring telemetry (only available for Staff or if an `ExamAccess` record exists).

| Field | Type | Description |
| :--- | :--- | :--- |
| `total_heartbeats` | Integer | Number of heartbeats received from the client. |
| `total_violations` | Integer | Total count of all violation events across all heartbeats. |
| `critical_violations` | Integer | Number of critical violations (e.g., MULTI_FACE). |
| `proctoring_integrity` | Float | Ratio of received heartbeats to expected heartbeats (0.0 - 1.0). |
| `average_suspicion` | Float | Average suspicion score across all heartbeats (0.0 - 1.0). |
| `auto_status` | String \| null | Automated status determined by the system. `null` if no heartbeats. |
| `status` | String \| null | Current proctoring status (manual override if exists). |
| `is_manually_reviewed` | Boolean | Whether an admin has manually reviewed this attempt. |
| `timeline_url` | URL | Absolute URL to the Integrity Audit timeline. |

#### `submissions` Array Item:
...
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
        "time_used": 2400,
        "violation_score": 0.05,
        "proctoring_status": "clear",
        "tie_break_reason": null,
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
    },
    "proctoring_summary": {
        "total_heartbeats": 12,
        "total_violations": 5,
        "critical_violations": 1,
        "proctoring_integrity": 1.0,
        "average_suspicion": 0.05,
        "auto_status": "clear",
        "status": "clear",
        "is_manually_reviewed": false,
        "timeline_url": "https://api.vmlc.edu/v2/exams/550e8400-e29b-41d4-a716-446655440000/candidates/6ba7b810-9dad-11d1-80b4-00c04fd430c8/integrity-audit/"
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
        "time_used": null,
        "violation_score": 0.0,
        "proctoring_status": null,
        "tie_break_reason": null,
        "recorded_at": null,
        "auto_score": false,
        "started_at": null,
        "submitted_at": null,
        "face_capture": null,
        "submissions": []
    },
    "proctoring_summary": null
}
```
