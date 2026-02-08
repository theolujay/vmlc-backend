# Candidate Dashboard API Documentation

This document defines the response structure for the student-facing dashboard. It is designed to give the frontend everything it needs in a single request to render the candidate's home screen.

## Candidate Dashboard
`GET /v1/competition/dashboard/candidate/`

Provides a comprehensive overview for the student, including their notifications, current progress, active exam, and historical performance.

### Response Body (`200 OK`)
```json
{
  "candidate_context": {
    "full_name": "John Doe",
    "role": "screening",
    "profile_picture": "https://api.vmlc.com/media/profs/john.jpg",
    "is_setup_complete": true,
    "status": "active",
    "notifications": {
      "info": [
        {
          "id": 1,
          "message": "Stay sharp! The league round 3 begins tomorrow."
        }
      ],
      "success": [],
      "error": []
    }
  },
  "enrollment_stage_progress": {
    "current_stage": "league", 
    "current_round": 3,
    "total_rounds": 6,
    "published_rounds": 2,
    "has_taken_current_round": false,
    "qualification_status": {
      "is_qualified": true,
      "advancement_policy": {
          "mode": "top_percent",
          "value": 0.3
      },
      "message": "You have qualified for the League Stage!"
    }
  },
  "active_exam": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "title": "League Round 3",
    "stage": "league",
    "round": 3,
    "question_count": 30,
    "starts_at": "2026-01-31T08:00:00Z",
    "ends_at": "2026-01-31T20:00:00Z",
    "duration_minutes": 60,
    "status": "ongoing",
    "attempt": {
      "started_at": "2026-01-31T19:00:00Z",
      "deadline": "2026-01-31T20:00:00Z",
      "submitted_at": "2026-01-31T19:35:00Z"
    },
    "access_status": "started"
  },
  "performance": {
    "screening_ranking": {
      "rank": 45,
      "total_candidates": 10230,
      "score": 88.5,
      "percentile": 99.5,
      "exam_id": "screening-exam-uuid",
      "exam_title": "Screening Exam 2026"
    },
    "league_leaderboard": {
      "overall_rank": 12,
      "total_candidates": 850,
      "total_score": 175.5,
      "rank_change": 2, 
      "as_of_round": 2,
      "is_active": true
    },
    "final_ranking": {
      "rank": 5,
      "total_candidates": 50,
      "score": 95.0,
      "percentile": 90.0,
      "exam_id": "final-exam-uuid",
      "exam_title": "Grand Finale"
    }
  },
  "exam_history": [
    {
      "exam_id": "screening-uuid",
      "exam_title": "Screening Exam",
      "stage": "screening",
      "round": null,
      "score": 88.5, 
      "percentage": 88.5, 
      "date": "2026-01-15T10:00:00Z",
      "status": "concluded",
      "is_published": true
    }
  ]
}
```

### Key Field Definitions:

#### Active Exam Statuses
The `status` field in `active_exam` tells the frontend what to display:
- `scheduled`: The exam is coming up but hasn't started yet.
- `ongoing`: The exam is currently open and can be taken.
- `awaiting_results`: The student has finished the exam, but the official results aren't out yet.
- `results_published`: Official results for this specific exam are now available.

#### Access Status
The `access_status` tracks the student's personal interaction with the exam:
- `null`: Student hasn't interacted with it yet.
- `started`: Student has entered the exam and their timer is running.
- `submitted`: Student has successfully handed in their answers.

#### Performance Snapshot
- `screening_ranking` & `final_ranking`: These are "one-off" results for the major entry and exit stages.
- `league_leaderboard`: This is a cumulative table that updates round-by-round. `is_active` indicates if the candidate currently has a finalized rank for the reported round.

---

## Take Exam (V2)
`GET /v2/exams/<uuid:exam_id>/take-exam/`

Returns the exam details and questions for a candidate to start the exam. 

### Behavioral Note:
Calling this endpoint marks the exam as **"started"** for the student. The personal countdown begins immediately.

---

## Submit Exam Answers (V2)
`POST /v2/exams/<uuid:exam_id>/submit/`

Submits all answers for a specific exam.

### Behavioral Note:
Once submitted, the system automatically triggers a background scoring process. The dashboard cache is cleared immediately so the student sees their updated status.

---

## Important System Rules for Frontend

1.  **Cache Invalidation**: The dashboard is cached for 1 hour by default. However, it is **automatically cleared** whenever:
    - A student submits an exam.
    - Staff members publish new results/ranking.
    - A student's profile or status is updated.
2.  **Grace Period**: Students have a **5-minute grace period** after their personal timer ends to account for network latency during submission.
3.  **Result Visibility**: In the `exam_history`, the `score` and `percentage` will remain `null` until the staff officially publishes the results. This prevents students from seeing unverified or "leaked" scores before they are finalized.