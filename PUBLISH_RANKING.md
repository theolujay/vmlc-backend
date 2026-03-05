# Publish Ranking Snapshot API

This endpoint is used by Staff (specifically Superadmins for publishing) to generate, publish, or schedule the publication of ranking snapshots for a specific exam.

**Endpoint:** `POST /competition/rankings/publish/`  
**Authentication:** Required (Staff Token)  
**Permissions:** `ActiveAdminPermissions` (Generation), `ActiveSuperadminPermissions` (Publishing/Scheduling)

---

## Request Schema

The request is a JSON object with the following fields:

| Field | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `exam_id` | `uuid` | **Yes** | - | The unique identifier of the concluded exam. |
| `publish_now` | `boolean` | No | `false` | If `true`, immediately publishes the existing active ranking snapshot. |
| `publish_at` | `iso8601` | No | `null` | A future timestamp to schedule the publication. If provided, `publish_now` is ignored. |

### Operational Logic
1.  **Generation Only**: If both `publish_now` and `publish_at` are omitted (or false/null), the system will simply trigger the background task to **generate** a new ranking snapshot.
2.  **Immediate Publish**: If `publish_now` is `true`, the system immediately releases the active snapshot to candidates.
3.  **Scheduled Publish**: If `publish_at` is provided, the system schedules a background task to release the snapshot at the specified time.

---

## Responses

### 1. Generation Started
**Status:** `202 Accepted`
```json
{
  "message": "Ranking snapshot generation has been started."
}
```

### 2. Published Successfully
**Status:** `202 Accepted`
```json
{
  "message": "Ranking snapshot published."
}
```

### 3. Scheduled Successfully
**Status:** `202 Accepted`
```json
{
  "message": "Ranking snapshot scheduled for publication at 2026-03-10T10:00:00Z."
}
```

### 4. Errors
- **400 Bad Request**: 
    - `{"error": "No active ranking snapshot available to publish."}` (Occurs if trying to publish/schedule before a ranking is generated).
    - `{"error": "publish_at must be in the future."}`
    - `{"detail": "This exam isn't yet concluded"}`
- **403 Forbidden**: `{"detail": "You do not have permissions to publish rankings"}` (Occurs if a non-Superadmin tries to publish/schedule).
- **404 Not Found**: `{"detail": "Exam not found."}`

---

## Notes for UI
- **Metadata Visibility**: When a ranking is scheduled, the `RankingSnapshot` object's `meta` field will include `scheduled_publish_at`. You can use this to show a "Scheduled" status on the staff dashboard.
- **League Leaderboards**: Publishing a ranking for a **League** stage automatically triggers an update of the cumulative leaderboard.
- **Cache Invalidation**: Publishing automatically invalidates candidate-facing dashboard caches.
