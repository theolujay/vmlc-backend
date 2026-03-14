# Exam Time Sync API

## Overview

The Exam Time Sync API provides server-accurate time information for exam timers. This endpoint allows the client to sync with server time instead of relying on the device's clock, which helps prevent cheating through clock manipulation.

## Endpoint

```
GET /v2/exams/<exam_id>/time/
```

### URL Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `exam_id` | UUID | The unique identifier of the exam |

### Headers

| Header | Value | Required |
|--------|-------|----------|
| Authorization | Bearer `<token>` | Yes |

### Response

#### Success (200 OK)

```json
{
    "server_time": "2024-01-15T10:30:00Z",
    "deadline": "2024-01-15T11:30:00Z",
    "remaining_seconds": 3600
}
```

| Field | Type | Description |
|-------|------|-------------|
| `server_time` | ISO 8601 datetime | Current server timestamp |
| `deadline` | ISO 8601 datetime | Exam submission deadline |
| `remaining_seconds` | integer | Seconds remaining until deadline (minimum 0) |

#### Error Responses

**401 Unauthorized** - Invalid or missing authentication token

**403 Forbidden** - User is not eligible to take the exam

```json
{
    "detail": "You do not have access to this exam."
}
```

**404 Not Found** - Exam not found

```json
{
    "detail": "Exam not found."
}
```

## Usage

### Timer Sync Strategy

1. **On Exam Load**: Call this endpoint to get the initial `deadline` and `remaining_seconds`
2. **Periodic Sync**: Call this endpoint every ~30 seconds to sync with server time
3. **Calculate Remaining**: Use `remaining_seconds = deadline - server_time` (not client clock)
4. **Handle Expiry**: When `remaining_seconds` reaches 0, auto-submit or show expiry UI

### Example Implementation (JavaScript)

```javascript
let deadline = null;
let serverTimeSyncInterval = null;

async function syncTime(examId) {
    const response = await fetch(`/v2/exams/${examId}/time/`, {
        headers: {
            'Authorization': `Bearer ${authToken}`
        }
    });
    
    if (!response.ok) {
        throw new Error('Failed to sync time');
    }
    
    const data = await response.json();
    deadline = new Date(data.deadline);
    
    return {
        remainingSeconds: data.remaining_seconds,
        deadline: deadline
    };
}

function startTimeSync(examId) {
    // Initial sync
    syncTime(examId);
    
    // Sync every 30 seconds
    serverTimeSyncInterval = setInterval(() => {
        syncTime(examId);
    }, 30000);
}

function stopTimeSync() {
    if (serverTimeSyncInterval) {
        clearInterval(serverTimeSyncInterval);
    }
}

function getRemainingSeconds() {
    if (!deadline) return 0;
    
    const now = new Date();
    const remaining = Math.floor((deadline - now) / 1000);
    return Math.max(0, remaining);
}
```

## Security Considerations

- The endpoint requires authentication (candidate must be logged in)
- Validates that the candidate has access to the exam
- Checks exam status (rejects submitted/expired/failed exams)
- Returns server time only after exam has started (validates `started_at` and `deadline`)

## Benefits

1. **Prevents Clock Manipulation**: Server time cannot be changed by client device
2. **Timezone Independent**: Server doesn't care about client's timezone
3. **Multi-tab Support**: All tabs sync to same server time
4. **Accurate Deadline**: Deadline is always based on server's understanding of time
