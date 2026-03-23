# Live Candidate Exam Status API - Proposal

## Goal
Provide staff with a real-time view of candidates currently taking an exam, including exam attempt status, timer, heartbeat/proctoring data, and progress.

## Data Available

| Source | Fields |
|--------|--------|
| `ExamAccess` | status, started_at, deadline, submitted_at, facilitator_system, proctoring_status |
| `Exam` | id, title, description, scheduled_date, open_duration_hours, countdown_minutes, status |
| `CandidateAnswer` | question, selected_option, answered_at (for progress calculation) |
| `ExamHeartbeat` | sequence_number, timestamp, suspicion_score, summary (violation counts), meta |
| `ViolationEvent` | event_type, is_critical, timestamp, metadata |

## Proposed Endpoint

```
GET /api/v2/exams/<exam_id>/candidates/<candidate_id>/live-status/
```

**Access**: Staff with appropriate permissions (ActiveModeratorPermissions or similar)

## Response Schema

```json
{
  "exam": {
    "id": "uuid",
    "title": "string",
    "status": "ongoing|scheduled|concluded",
    "duration_minutes": 60,
    "starts_at": "datetime",
    "ends_at": "datetime"
  },
  "attempt": {
    "status": "started|submitted|expired|failed",
    "started_at": "datetime",
    "deadline": "datetime",
    "submitted_at": "datetime|null",
    "time_remaining_seconds": 1800,
    "time_used_seconds": 1200
  },
  "progress": {
    "questions_attempted": 45,
    "questions_total": 60,
    "percent_complete": 75.0
  },
  "proctoring": {
    "status": "clean|flagged|suspicious",
    "suspicion_score": 0.15,
    "last_heartbeat_at": "datetime",
    "heartbeat_sequence": 24,
    "violations": {
      "total": 3,
      "critical": 1,
      "by_type": {
        "TAB_SWITCH": 2,
        "FULLSCREEN_EXIT": 1
      }
    },
    "recent_events": [
      {"type": "TAB_SWITCH", "timestamp": "...", "is_critical": false, "metadata": {...}}
    ]
  }
}
```

## Implementation Approach

1. **Create a new endpoint** in `vmlc/v2/views/exam.py` or create a dedicated views file
2. **Add serializer** to format the live status response
3. **Permission class** - Reuse `ActiveModeratorPermissions` or create new
4. **Query optimization** - Use `select_related` and `prefetch_related` to minimize DB queries:
   - `ExamAccess.objects.select_related('exam', 'candidate__user')`
   - `ExamHeartbeat.objects.filter(...)` for latest heartbeat
   - `ViolationEvent.objects.filter(...)` for recent violations
5. **Add caching** - Short TTL (5-10s) for frequently polled data

## Edge Cases

- **No ExamAccess**: Return 404 - candidate not assigned to this exam
- **Exam not ongoing**: Return current state even if concluded (for review)
- **No heartbeats**: Show "no heartbeat received" status
- **Candidate offline**: Use existing `user_online_{id}` cache pattern

## Alternative: WebSocket

For true real-time updates, consider WebSocket connection via Django Channels. This would push updates on heartbeat events rather than polling. However, polling via REST is simpler to implement first.

---

**Approve?** Let me know if you want any modifications to the schema or approach.