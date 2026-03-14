# Proposal: Efficient Periodic Proctoring Heartbeat (v2)

To optimize performance and minimize individual server pings, we propose a unified **Heartbeat** mechanism. This replaces high-frequency individual pings with a single, consolidated request every 5 minutes that combines violation telemetry with mandatory visual evidence.

## 📡 API Specification

### Endpoint: `POST /v2/exams/{exam_id}/heartbeat/`
**Frequency:** Every 300 seconds (5 minutes)
**Method:** `POST`
**Content-Type:** `multipart/form-data`

#### Fields:
1. **`payload`** (JSON string): Consolidated summary, event log, and client metadata.
2. **`face_capture`** (File/JPEG): A representative frame captured during the current interval.

#### Payload Structure:
```json
{
  "sequence_number": 1,
  "client_uuid": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "timestamp": "2026-03-14T10:05:00Z",
  "period_start": "2026-03-14T10:00:00Z",
  "period_end": "2026-03-14T10:05:00Z",
  "meta": {
    "os": "MacOS",
    "browser": "Chrome 122",
    "screen_resolution": "1920x1080",
    "battery_level": 0.85,
    "is_charging": true,
    "network_latency_ms": 120
  },
  "summary": {
    "TAB_SWITCH": 2,
    "SCREENSHOT": 0,
    "FULLSCREEN_EXIT": 1,
    "MULTI_FACE": 12,
    "NO_FACE": 45,
    "ATTENTION_LAPSE": 30
  },
  "events": [
    {
      "type": "TAB_SWITCH",
      "timestamp": "2026-03-14T10:02:15Z",
      "metadata": { "duration_seconds": 15, "question_id": 102 }
    }
  ]
}
```

## 🛠️ Proposed Client Implementation

### 1. `sequence_number` & `client_uuid`
- The client MUST track the number of heartbeats sent (starting from 1).
- Each heartbeat MUST have a unique `client_uuid`. This ensures that if a network retry occurs, the backend can safely ignore the duplicate without counting it twice.

### 2. Environmental Metadata (`meta`)
- To provide context for "No Face" detections (e.g., lag or system stress), the client will include battery status and network latency in the `meta` object.

### 3. Submission Sync
- A "Final Heartbeat" MUST be sent immediately upon exam submission, even if the 5-minute timer hasn't expired. This ensures all final events are captured.

### 4. Resiliency (Offline Mode)
- If a heartbeat fails, the payload (including the `face_capture` Blob/Base64) is saved to `IndexedDB` or `localStorage`. 
- The next heartbeat will attempt to send both the current data and the failed bucket.

## 📊 Benefits

- **Audit Integrity**: `sequence_number` allows proctors to see if the candidate intentionally went "offline" to hide activity.
- **Fairness Context**: High latency or low battery metadata helps distinguish between intentional cheating and technical difficulties.
- **Efficiency**: Reduces network traffic while maintaining a high-fidelity "Black Box" recorder of the candidate's environment.
