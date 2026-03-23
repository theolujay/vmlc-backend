# Ranking API Specification

## RetrieveRankingSnapshotView

Retrieves the full ranking snapshot for an exam, including all candidate entries.

### Endpoint

```
GET /api/competition/rankings/<exam_id>/
```

### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `exam_id` | UUID | The exam's unique identifier |

### Response

```json
{
  "id": "uuid",
  "competition": "uuid",
  "stage": "string",
  "stage_display": "string",
  "round": 1,
  "exam": "uuid",
  "facilitator_system": "vmlc",
  "is_published": true,
  "published_at": "2026-03-21T12:00:00Z",
  "meta": {
    "generated_by": "uuid",
    "ranking_policy": "standard",
    "tie_break_strategy": null
  },
  "created_at": "2026-03-21T12:00:00Z",
  "entries": [
    {
      "candidate": "uuid",
      "candidate_info": {
        "id": "uuid",
        "full_name": "John Doe",
        "email": "john@example.com",
        "state": "Lagos",
        "school_name": "ABC High School",
        "school_type": "public",
        "current_class": "SSS3"
      },
      "exam_score": 85.50,
      "rank": 1,
      "percentile": 95.0,
      "time_used": 3600,
      "tie_break_reason": null,
      "violation_score": 0.0,
      "proctoring_status": "clear",
      "attempt_status": "present"
    }
  ]
}
```

### Entry Fields

| Field | Type | Description |
|-------|------|-------------|
| `candidate` | UUID | Candidate's unique identifier |
| `candidate_info` | object | Candidate's profile details |
| `exam_score` | float | The candidate's exam score (0.0 if absent) |
| `rank` | int | Assigned rank position |
| `percentile` | float | Percentile rank (0-100) |
| `time_used` | int | Time taken in seconds (null if absent) |
| `tie_break_reason` | string | Explanation if tie-break was applied |
| `violation_score` | float | Weighted average of proctoring suspicion scores |
| `proctoring_status` | string | Proctoring verdict: `clear`, `suspicious`, or `flagged` |
| `attempt_status` | string | Participation status: `present`, `absent`, or `disqualified` |

### Proctoring Status Values

| Value | Condition |
|-------|-----------|
| `clear` | Average suspicion < 0.3, no critical events |
| `suspicious` | Average suspicion >= 0.3 and < 0.7 |
| `flagged` | Average suspicion >= 0.7 OR any critical event (`MULTI_FACE`, `DEVTOOLS_OPEN`) |

### Attempt Status Values

| Value | Description |
|-------|-------------|
| `present` | Candidate submitted the exam |
| `absent` | Eligible candidate did not submit |
| `disqualified` | Candidate was disqualified |

### Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 404 | No active ranking snapshot found for this exam |

---

## RetrieveCandidateRankingSnapshotEntryView

Retrieves detailed performance data for a specific candidate in a specific exam ranking.

### Endpoint

```
GET /api/competition/rankings/<exam_id>/candidate/<candidate_id>/
```

### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `exam_id` | UUID | The exam's unique identifier |
| `candidate_id` | UUID | The candidate's unique identifier |

### Response (Present Candidate)

```json
{
  "exam_details": {
    "id": "uuid",
    "title": "First Round Examination",
    "stage": "preliminary",
    "round": 1,
    "scheduled_date": "2026-03-15",
    "concluded_at": "2026-03-15T18:00:00Z",
    "total_questions": 50,
    "total_candidates": 100,
    "average_score": 65.50
  },
  "candidate_info": {
    "id": "uuid",
    "full_name": "John Doe",
    "email": "john@example.com",
    "state": "Lagos",
    "school_name": "ABC High School",
    "school_type": "public",
    "current_class": "SSS3"
  },
  "candidate_performance": {
    "score": 85.50,
    "rank": 1,
    "percentile": 95.0,
    "recorded_at": "2026-03-15T17:30:00Z",
    "auto_score": true,
    "submissions": [
      {
        "question": {
          "id": "uuid",
          "text": "What is 2 + 2?",
          "image": null,
          "option_a": "3",
          "option_b": "4",
          "option_c": "5",
          "option_d": "6",
          "correct_answer": "B",
          "difficulty": "easy",
          "related_exams_count": 5,
          "created_at": "2026-01-01T00:00:00Z",
          "created_by": { ... },
          "updated_at": "2026-01-01T00:00:00Z",
          "updated_by": null
        },
        "selected_option": "B",
        "answered_at": "2026-03-15T17:01:23Z"
      }
    ],
    "time_used": 3600,
    "tie_break_reason": null,
    "started_at": "2026-03-15T16:00:00Z",
    "submitted_at": "2026-03-15T17:00:00Z",
    "face_capture": "/media/face_captures/uuid.jpg"
  },
  "proctoring_summary": {
    "total_heartbeats": 120,
    "total_violations": 2,
    "critical_violations": 0,
    "proctoring_integrity": 98.5,
    "integrity_flags": [],
    "average_suspicion": 0.05,
    "auto_status": "clear",
    "status": "clear",
    "is_manually_reviewed": false,
    "timeline_url": "/v2/exams/<exam_id>/candidates/<candidate_id>/integrity-audit/"
  }
}
```

### Response (Absent Candidate)

```json
{
  "exam_details": { ... },
  "candidate_info": { ... },
  "candidate_performance": {
    "score": 0.0,
    "attempt_status": "absent",
    "rank": 100,
    "percentile": 5.0,
    "time_used": null,
    "tie_break_reason": null,
    "recorded_at": null,
    "auto_score": false,
    "submissions": [],
    "started_at": null,
    "submitted_at": null,
    "face_capture": null
  },
  "proctoring_summary": null
}
```

### Proctoring Summary Fields

| Field | Type | Description |
|-------|------|-------------|
| `total_heartbeats` | int | Number of heartbeat signals received |
| `total_violations` | int | Total violation events detected |
| `critical_violations` | int | Count of critical violations (`MULTI_FACE`, `DEVTOOLS_OPEN`) |
| `proctoring_integrity` | float | Integrity score (0-100) |
| `integrity_flags` | array | List of integrity flag descriptions |
| `average_suspicion` | float | Weighted average suspicion score (0-1) |
| `auto_status` | string | Auto-determined status: `clear`, `suspicious`, or `flagged` |
| `status` | string | Current status (may be manually overridden) |
| `is_manually_reviewed` | boolean | Whether staff has manually reviewed this attempt |
| `timeline_url` | string | URL to the integrity audit timeline |

### Question Fields in Submissions

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Question identifier |
| `text` | string | The question text |
| `image` | string | Optional image URL |
| `option_a` - `option_d` | string | Answer options |
| `correct_answer` | string | Correct answer letter (A-D) |
| `difficulty` | string | Difficulty level |
| `related_exams_count` | int | Number of exams containing this question |
| `created_at` | datetime | When the question was created |
| `created_by` | object | Staff user who created the question |
| `updated_at` | datetime | Last modification time |
| `updated_by` | object | Staff user who last modified |

### Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 404 | Candidate not found in this ranking board |
