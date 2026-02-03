# Candidate Dashboard API Documentation

This document defines the optimal response structure for the student-facing dashboard to ensure efficient rendering and a seamless user experience.

<!-- http://localhost:8000/v1/notifications/2/mark-as-read/ -->

## Candidate Dashboard
`GET /v1/competition/dashboard/candidate/`

Provides a comprehensive overview for the student, including their current standing, upcoming tasks, and historical performance.

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
  "stage_progress": {
    "current_stage": "league", 
    "current_round": 3,
    "total_rounds": 6,
    "published_rounds": 2,
    "has_taken_current_round": false,
    "qualification_status": {
      "is_qualified": true,
      "advancement_policy": {
          "mode": "top_percent",
          "value": 0.3,
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
    "status": "scheduled", // Can be "ongoing", "scheduled", or "awaiting_results"
    "has_participated": false
  },
  "performance_snapshot": {
    "screening_standing": {
      "rank": 45,
      "total_candidates": 10230,
      "score": 88.5,
      "percentile": 99.5
    },
    "league_leaderboard": {
      "overall_rank": 12,
      "total_candidates": 850,
      "total_score": 175.5,
      "rank_change": 2, 
      "as_of_round": 2
    }
  },
  "exam_history": [
    {
      "exam_id": "screening-uuid",
      "exam_title": "Screening Exam",
      "stage": "screening",
      "round": null,
      "score": 88.5, // Null if not published
      "percentage": 88.5, // Null if not published
      "date": "2026-01-15T10:00:00Z",
      "status": "concluded",
      "is_published": true
    },
    {
      "exam_id": "league-r1-uuid",
      "exam_title": "League - Round 1",
      "stage": "league",
      "round": 1,
      "score": 92.0,
      "percentage": 92.0,
      "date": "2026-01-22T10:00:00Z",
      "status": "concluded",
      "is_published": true
    }
  ]
}
```

## Take Exam (V2)
`GET /v2/exams/<uuid:exam_id>/take-exam/`

Returns the exam details and questions for a candidate to start the exam. Supports LaTeX for mathematical content. 

### Response Body (`200 OK`)
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "League Round 3",
  "description": "This is the third round of the league stage.",
  "open_duration_hours": 12,
  "scheduled_date": "2026-01-31T08:00:00Z",
  "countdown_minutes": 60,
  "questions": [
    {
      "id": 3,
      "text": "What is the value of $x$ in the equation $2x + 5 = 15$?",
      "option_a": "$5$",
      "option_b": "$10$",
      "option_c": "$7.5$",
      "option_d": "$20$"
    },
    {
      "id": 5,
      "text": "Identify the integral: $\\\\int_{0}^{1} x^2 \\\\, dx$",
      "option_a": "$1/3$",
      "option_b": "$1/2$",
      "option_c": "$1$",
      "option_d": "$0$"
    }
  ]
}
```

## Submit Exam Answers (V2)
`POST /v2/exams/<uuid:exam_id>/submit/`

Submit all answers for a specific exam in bulk.

### Request Body
```json
{
  "answers": [
    {
      "question": 3,
      "selected_option": "a"
    },
    {
      "question": 5,
      "selected_option": "a"
    }
  ]
}
```

### Response Body (`201 Created`)
```json
{
  "message": "Answers submitted successfully!"
}
```

### Behavioral Notes:
1.  **Dashboard Caching**: The candidate dashboard response is cached for **1 hour** (`ttl=3600`) per candidate. Changes to notifications or status may not be immediate.
2.  **Exam Access Tracking**: Calling the `take-exam` endpoint marks the exam as `STARTED` for the candidate. This triggers the personal countdown timer. Re-entry is allowed until submission or expiration.
3.  **Submission Deadlines**: Submissions are accepted if the exam is globally open **OR** if the candidate is within their personal countdown (plus a **5-minute grace period**).
4.  **Result Visibility**: In the `exam_history`, `score` and `percentage` will be `null` until the standings for that exam are officially **published** by staff.
5.  **Awaiting Results**: If an exam is concluded and participated in but standings aren't published, the `active_exam` status will show as `awaiting_results`.


### Architectural Benefits:
1.  **Unified State**: Consolidates `candidate_info`, `stage_progress`, and `active_exam` into a single call to prevent waterfall loading.
2.  **Backend-Driven Logic**: The `qualification_status` and `notifications` objects allow the backend to manage business rules and messaging dynamically.
3.  **Real-time Indicators**: Includes `rank_change` directly in the snapshot to support "improved/dropped" UI elements without extra client-side calculations.
4.  **Action-Ready**: `active_exam` provides all necessary metadata to control the "Start Exam" triggers and timers.
