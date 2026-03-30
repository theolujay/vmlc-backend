# Live Candidate Exam Status API

This API provides staff with a real-time view of a candidate's progress and integrity status during an active exam attempt.

## REST Endpoint

**GET** `/api/v2/exams/<uuid:exam_id>/candidates/<uuid:candidate_id>/live-status/`

### Access Control
- **Permissions**: Requires Staff with `ActiveAdminPermissions`.
- **Authentication**: JWT Required.

---

## Real-time Updates via WebSocket

Live exam telemetry is automatically broadcasted to helpdesk thread groups when a candidate sends a heartbeat or violation event. This allows staff to monitor exam attempts in real-time without polling.

### Subscription
To receive live updates, staff must subscribe to the specific Helpdesk Thread over the Unified WebSocket:

1.  **Connect** to `ws/unified/`
2.  **Send Action**:
    ```json
    {
      "action": "subscribe_thread",
      "data": { "thread_id": "uuid" }
    }
    ```

### Message Format
When telemetry is updated, the server pushes a message with type `helpdesk.thread.exam_telemetry`:

```json
{
  "type": "helpdesk.thread.exam_telemetry",
  "data": {
    "exam": { ... },
    "attempt": { ... },
    "progress": { ... },
    "proctoring": { ... }
  }
}
```
*The `data` object follows the standard Response Schema defined below.*

---

## Response Schema (REST & WebSocket)

```json
{
  "exam": {
    "id": "uuid",
    "title": "string",
    "status": "ongoing | scheduled | concluded | cancelled | draft",
    "duration_minutes": 60,
    "starts_at": "datetime (ISO 8601)",
    "ends_at": "datetime (ISO 8601) | null"
  },
  "attempt": {
    "status": "pending | issued | started | submitted | expired | failed",
    "started_at": "datetime (ISO 8601) | null",
    "deadline": "datetime (ISO 8601) | null",
    "submitted_at": "datetime (ISO 8601) | null",
    "time_remaining_seconds": 1800,
    "time_used_seconds": 1200
  },
  "progress": {
    "questions_attempted": 45,
    "questions_total": 60,
    "percent_complete": 75.0
  },
  "proctoring": {
    "status": "clear | suspicious | flagged | null",
    "suspicion_score": 0.15,
    "last_heartbeat_at": "datetime (ISO 8601) | null",
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
      {
        "type": "TAB_SWITCH",
        "timestamp": "2026-03-30T14:20:00Z",
        "is_critical": false,
        "metadata": {}
      }
    ]
  }
}
```

---

## Data Field Descriptions

### Exam Object
- `status`: The global lifecycle state of the exam blueprint.
- `duration_minutes`: The total time allowed for the attempt once started.
- `ends_at`: The calculated conclusion time based on `starts_at` + `open_duration_hours`.

### Attempt Object
- `status`: The candidate's specific execution state.
- `time_remaining_seconds`: Live countdown based on the server-side `deadline`.
- `time_used_seconds`: Cumulative time elapsed since `started_at`.

### Progress Object
- `questions_attempted`: Number of questions currently saved to the database.
- `percent_complete`: Percentage of the exam completed based on total questions.

### Proctoring Object
- `status`: The current automated or manual proctoring state.
- `suspicion_score`: A normalized score (0.0 to 1.0) indicating the likelihood of malpractice.
- `heartbeat_sequence`: The sequence number of the most recent telemetry packet received.
- `violations.by_type`: A breakdown of all recorded violations for this specific attempt.
- `recent_events`: A list of the 10 most recent violation events detected.

---

## Helpdesk Integration (REST)

This same data structure is available to Helpdesk staff when viewing thread details via REST. It is nested under the `candidate_live_exam_status` field in the **Helpdesk Thread Detail API**:

**GET** `/api/comms/helpdesk/staff/threads/<uuid:thread_id>/`

The system automatically identifies the candidate's most recent active exam attempt and provides this real-time snapshot to the support agent.

---

## Notes & Performance
- **Caching**: The REST endpoint utilizes short-term server-side caching (5-10s) for proctoring summaries to optimize performance under high-frequency polling. WebSocket updates are pushed immediately upon event processing.
- **Offline Detection**: Use the `is_candidate_online` field in the Helpdesk list/detail views to verify if the candidate's browser currently has an active WebSocket connection.
