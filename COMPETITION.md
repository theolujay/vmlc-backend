# Competition API Documentation

This document provides detailed information on the response bodies for the competition endpoints defined in `competition/urls.py`.

## Endpoints Summary

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| **POST** | `/competition/rankings/publish/` | Trigger asynchronous generation/publishing of rankings. |
| **GET** | `/competition/rankings/{exam_id}/` | Retrieve specific ranking with detailed entries using Exam ID. |
| **GET** | `/competition/rankings/{exam_id}/candidate/{candidate_id}/` | Retrieve detailed performance for a specific candidate in an exam ranking. |
| **GET** | `/competition/leaderboard/league/` | Retrieve the latest cumulative league leaderboard. |
| **GET** | `/competition/leaderboard/league/candidate/{candidate_id}/` | Retrieve cumulative performance for a specific candidate in the league. |

---

## 1. Publish RankingSnapshot
`POST /competition/rankings/publish/`

Used by administrators to trigger the calculation of ranking for a specific exam round.

### Request Body
```json
{
  "exam_id": "550e8400-e29b-41d4-a716-446655440000",
  "publish_now": true
}
```

### Response Body (`202 Accepted`)
```json
{
  "message": "RankingSnapshot generation has been started."
}
```

---

## 2. Retrieve RankingSnapshot
`GET /competition/rankings/{exam_id}/`

Retrieves a snapshot of ranking for a specific stage and round using the Exam ID.

### Response Body (`200 OK`)
```json
{
  "id": 1,
  "competition": 1,
  "stage": "league",
  "stage_display": "League",
  "round": 1,
  "exam": "550e8400-e29b-41d4-a716-446655440000",
  "facilitator_system": "vmlc",
  "is_published": true,
  "published_at": "2026-01-30T10:00:00Z",
  "meta": {},
  "created_at": "2026-01-30T09:55:00Z",
  "entries": [
    {
      "candidate": "uuid-of-candidate",
      "candidate_name": "John Doe",
      "candidate_email": "john.doe@example.com",
      "school_name": "St. Peters College",
      "exam_score": "95.50",
      "rank": 1,
      "percentile": 100.0,
      "tie_break_reason": null
    }
  ]
}
```

---

## 3. Candidate Ranking Detail
`GET /competition/rankings/{exam_id}/candidate/{candidate_id}/`

Retrieves detailed performance for a specific candidate in a specific exam ranking, including their answers and the correct options.

### Response Body (`200 OK`)
```json
{
  "exam_details": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "title": "League Round 1",
    "stage": "league",
    "round": 1,
    "scheduled_date": "2026-01-30T08:00:00Z",
    "concluded_at": "2026-01-30T20:00:00Z",
    "total_questions": 50,
    "total_candidates": 1200,
    "average_score": 72.45
  },
  "candidate_performance": {
    "candidate": "uuid-of-candidate",
    "candidate_name": "John Doe",
    "candidate_email": "john.doe@example.com",
    "school_name": "St. Peters College",
    "score": "95.50",
    "rank": 1,
    "percentile": 100.0,
    "recorded_at": "2026-01-30T10:00:00Z",
    "auto_score": true,
    "submissions": [
      {
        "question": {
          "id": 1,
          "text": "What is 2+2?",
          "option_a": "3",
          "option_b": "4",
          "option_c": "5",
          "option_d": "6",
          "correct_answer": "B",
          "difficulty": "easy"
        },
        "selected_option": "B",
        "answered_at": "2026-01-30T10:05:00Z"
      }
    ]
  }
}
```

---

## 4. League Leaderboard
`GET /competition/leaderboard/league/`

Retrieves the latest cumulative leaderboard for the active competition's league stage. This combines scores from all published rounds.

### Response Body (`200 OK`)
```json
{
  "id": 5,
  "competition": 1,
  "stage": "league",
  "stage_display": "League",
  "as_of_round": 3,
  "created_at": "2026-01-30T15:00:00Z",
  "updated_at": "2026-01-30T15:05:00Z",
  "entries": [
    {
      "candidate": "uuid-of-candidate",
      "candidate_name": "John Doe",
      "candidate_email": "john.doe@example.com",
      "school_name": "St. Peters College",
      "total_score": "285.50",
      "overall_rank": 1,
      "rank_change": 0
    }
  ]
}
```

---

## 5. Candidate League Cumulative Detail
`GET /competition/leaderboard/league/candidate/{candidate_id}/`

Retrieves cumulative performance for a specific candidate in the latest league leaderboard.

### Response Body (`200 OK`)
```json
{
  "candidate": "uuid-of-candidate",
  "candidate_name": "John Doe",
  "candidate_email": "john.doe@example.com",
  "school_name": "St. Peters College",
  "total_score": "285.50",
  "overall_rank": 1,
  "rank_change": 0
}
```


## 6. Competition Dashboard
`GET /v1/competition/dashboard/`

Provides an aggregated view of competition statistics, progress, exam statuses, and ranking summaries.

### Response Body (`200 OK`)
```json
{
  "stats": {
    "enrolled": 1575,
    "active": 612,
    "eliminated": 636,
  },
  "progress": {
    "current_stage": "league",
    "current_round": 3,
    "total_rounds": 6,
    "published_rounds": 2
  },
  "exams": [
    {
      "id": "screening-uuid",
      "title": "Screening Exam",
      "stage": "screening",
      "status": "concluded",
      "ranking_status": "published",
      "stats": {
        "candidates_sat": 10230,
        "avg_score": 55.2
      },
    },
    {
      "id": "league-r1-uuid",
      "title": "League - Round 1",
      "stage": "league",
      "status": "concluded",
      "ranking_status": "published",
      "stats": {
        "candidates_sat": 850,
        "avg_score": 62.4,
        "absent": 200
      },
    }
  ],
  "leaderboard_summary": [
    // only top 3 rankings
    {
      "candidate": "uuid-1",
      "candidate_name": "Candidate A",
      "school_name": "St. Peters College",
      "total_score": "372.50",
      "overall_rank": 1,
      "rank_change": 0
    }
  ],
  "latest_ranking_summary": {
    // only top 3 rankings
    "exam_id": "league-r1-uuid",
    "exam_title": "League - Round 1",
    "entries": [
      {
        "candidate": "uuid-1",
        "candidate_name": "Candidate A",
        "exam_score": "95.50",
        "rank": 1,
        "percentile": 99.9
      }
    ]
  }
}