# Exam Heartbeat API

## Overview

The Exam Heartbeat API provides periodic proctoring telemetry during an exam attempt. Clients send heartbeat data at regular intervals containing violation events, screenshots, and client environment metadata. The server processes this data to calculate suspicion scores and detect potential cheating behaviors.

## Heartbeat Interval

- **Production**: Every 5 minutes
- **Development**: Every 1 minute (when `DEBUG=True`)

The client should send heartbeats at approximately this interval. The server accepts a tolerance of 30 seconds.

---

## Submit Heartbeat

### Endpoint

```
POST /v2/exams/<exam_id>/heartbeat/
```

### URL Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `exam_id` | UUID | The unique identifier of the exam |

### Headers

| Header | Value | Required |
|--------|-------|----------|
| Authorization | Bearer `<token>` | Yes |
| Content-Type | `multipart/form-data` | Yes |

### Request Body (Multipart Form Data)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `payload` | JSON string | Yes | Heartbeat data as a JSON string |
| `face_capture` | File | No | Optional face capture image for the period |

#### Payload Structure

```json
{
    "sequence_number": 1,
    "client_uuid": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2024-01-15T10:30:00Z",
    "period_start": "2024-01-15T10:25:00Z",
    "period_end": "2024-01-15T10:30:00Z",
    "summary": {
        "TAB_SWITCH": 2,
        "NO_FACE": 1
    },
    "meta": {
        "os": "Windows",
        "browser": "Chrome",
        "viewport_width": 1920,
        "viewport_height": 1080,
        "timezone": "America/New_York"
    },
    "events": [
        {
            "type": "TAB_SWITCH",
            "timestamp": "2024-01-15T10:26:00Z",
            "metadata": {
                "target_url": "https://google.com",
                "duration_ms": 5000
            }
        }
    ]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `sequence_number` | integer | Yes | Sequential index (starts at 1). Used to detect missing heartbeats. |
| `client_uuid` | UUID | Yes | Unique identifier for idempotency. Generated once per heartbeat on client. |
| `timestamp` | ISO 8601 datetime | Yes | Client-side timestamp when heartbeat was sent |
| `period_start` | ISO 8601 datetime | Yes | Start of the monitoring period |
| `period_end` | ISO 8601 datetime | Yes | End of the monitoring period |
| `summary` | JSON object | No | Aggregated counts of violation types detected in the period |
| `meta` | JSON object | No | Client environment metadata (OS, browser, screen dimensions, etc.) |
| `events` | Array | No | List of individual violation events captured during the period |

### Response

#### Success (200 OK)

```json
{
    "status": "ok",
    "sequence": 1
}
```

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | Always "ok" on success |
| `sequence` | integer | The sequence number that was received |

#### Error Responses

**400 Bad Request** - Invalid payload format or data

```json
{
    "non_field_errors": [
        "Heartbeat interval must be approximately 5 minutes. Got 2.0 minutes."
    ]
}
```

**403 Forbidden** - Exam not started or already submitted

```json
{
    "detail": "Heartbeat is only accepted for ongoing attempts."
}
```

---

## Violation Event Types

| Event Type | Weight | Description |
|------------|--------|-------------|
| `TAB_SWITCH` | 0.3 | User switched to a different browser tab/window |
| `MULTI_FACE` | 0.5 | Multiple faces detected in camera |
| `FULLSCREEN_EXIT` | 0.1 | User exited fullscreen mode |
| `NO_FACE` | 0.2 | No face detected in camera |
| `DEVTOOLS_OPEN` | 0.4 | Developer tools opened |
| `SCREENSHOT` | 0.1 | Screenshot detected |

### Suspicion Score Calculation

The suspicion score is calculated as a weighted sum of violation counts, using logarithmic scaling for high counts:

```
score = Σ(weight[event_type] × (1 + log10(count)))
```

The final score is capped at 1.0.

---

## Integrity Audit (Admin)

### Endpoint

```
GET /v2/exams/<exam_id>/candidates/<candidate_id>/integrity-audit/
```

### Headers

| Header | Value | Required |
|--------|-------|----------|
| Authorization | Bearer `<token>` | Yes (Admin) |

### Response

Returns detailed proctoring data including all heartbeats, violation events, timeline analysis, and summary statistics.

---

## Client Implementation

### JavaScript Example

```javascript
const HEARTBEAT_INTERVAL_MS = 5 * 60 * 1000; // 5 minutes
let sequenceNumber = 0;
let clientUuid = crypto.randomUUID();

async function sendHeartbeat(examId, summary, events, faceCapture = null) {
    sequenceNumber++;
    
    const now = new Date();
    const periodStart = new Date(now.getTime() - HEARTBEAT_INTERVAL_MS);
    
    const payload = {
        sequence_number: sequenceNumber,
        client_uuid: clientUuid,
        timestamp: now.toISOString(),
        period_start: periodStart.toISOString(),
        period_end: now.toISOString(),
        summary: summary,
        meta: {
            os: navigator.platform,
            browser: navigator.userAgent,
            viewport_width: window.innerWidth,
            viewport_height: window.innerHeight,
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
        },
        events: events
    };
    
    const formData = new FormData();
    formData.append('payload', JSON.stringify(payload));
    
    if (faceCapture) {
        formData.append('face_capture', faceCapture);
    }
    
    const response = await fetch(`/v2/exams/${examId}/heartbeat/`, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${authToken}`
        },
        body: formData
    });
    
    if (!response.ok) {
        const error = await response.json();
        console.error('Heartbeat failed:', error);
    }
    
    return response.json();
}

// Start periodic heartbeats when exam begins
function startHeartbeat(examId) {
    const summary = { TAB_SWITCH: 0, NO_FACE: 0 };
    const events = [];
    
    // Initial heartbeat
    sendHeartbeat(examId, summary, events);
    
    // Set up interval for subsequent heartbeats
    return setInterval(() => {
        sendHeartbeat(examId, summary, events);
    }, HEARTBEAT_INTERVAL_MS);
}
```

### Summary Tracking

The client should maintain a running summary of violations detected between heartbeats:

```javascript
const violationSummary = {
    TAB_SWITCH: 0,
    MULTI_FACE: 0,
    FULLSCREEN_EXIT: 0,
    NO_FACE: 0,
    DEVTOOLS_OPEN: 0,
    SCREENSHOT: 0
};

function onTabSwitch() {
    violationSummary.TAB_SWITCH++;
}

function onNoFaceDetected() {
    violationSummary.NO_FACE++;
}

// Reset summary after each heartbeat
function sendHeartbeatWithSummary(examId) {
    const events = []; // Individual events for this period
    const summary = { ...violationSummary };
    
    sendHeartbeat(examId, summary, events);
    
    // Reset for next interval
    Object.keys(violationSummary).forEach(key => {
        violationSummary[key] = 0;
    });
}
```

## Data Storage

### ExamHeartbeat Model

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Primary key |
| `exam_access` | ForeignKey | Link to the exam attempt |
| `sequence_number` | integer | Sequential index |
| `client_uuid` | UUID | Idempotency key |
| `timestamp` | DateTime | Server timestamp when received |
| `period_start` | DateTime | Start of monitoring period |
| `period_end` | DateTime | End of monitoring period |
| `summary` | JSON | Aggregated violation counts |
| `face_capture` | ImageFile | Optional face capture |
| `suspicion_score` | float (0.0-1.0) | Computed suspicion score |
| `meta` | JSON | Client environment metadata |

### ViolationEvent Model

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Primary key |
| `heartbeat` | ForeignKey | Link to parent heartbeat |
| `event_type` | string | Type of violation |
| `timestamp` | DateTime | When the violation occurred |
| `is_critical` | boolean | Whether event is critical |
| `metadata` | JSON | Event-specific data |

## Proctoring Status

After processing heartbeats, the exam attempt's `proctoring_status` is updated automatically:

| Status | Description |
|--------|-------------|
| `clear` | No violations detected |
| `warning` | Minor violations detected |
| `flagged` | Significant violations detected |
| `review` | Manual review required |

The status can be manually overridden by admins. Once manually reviewed, automatic updates stop.
