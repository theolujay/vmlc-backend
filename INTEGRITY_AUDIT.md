# Proposal: Integrity Audit Dashboard & Ranking Integration

This document outlines how the **Heartbeat** and **Violation** data will be synthesized into a proctoring workflow for administrators.

## 1. Goal: High-Level Insight to Deep-Dive Audit

The proctoring workflow follows a three-step triage process:
1.  **Ranking View:** Admins see a list of top candidates sorted by score but filtered by "Suspicion Score."
2.  **Summary View:** Admins click a candidate to see their performance details + a proctoring summary.
3.  **Audit Dashboard:** Admins perform a deep-dive audit of the candidate's entire heartbeat timeline.

---

## 2. Ranking Snapshot Integration

To enable quick filtering, we will update the `RankingSnapshotEntry` model in the `competition` app.

### Model Changes (`competition.models.RankingSnapshotEntry`)
-   **`violation_score`** (Float, default=0.0): An average of all heartbeat `suspicion_score`s for that candidate's attempt.
-   **`proctoring_status`** (CharField, default='clear'): One of `clear`, `suspicious`, `flagged`.

### Serializer Changes (`competition.serializers.RankingSnapshotEntrySerializer`)
Updating `RetrieveRankingSnapshotView` to include these fields allows the UI to highlight suspicious candidates directly on the leaderboard.

```json
{
  "rank": 1,
  "candidate_info": { "full_name": "John Doe", ... },
  "exam_score": 95,
  "violation_score": 0.82,
  "proctoring_status": "suspicious"
}
```

---

## 3. Quick Insight: `RetrieveCandidateRankingSnapshotEntryView`

When viewing a specific candidate's result detail, the backend will provide a `proctoring_summary`. This allows an admin to decide if a deep-dive is necessary.

**Added Fields:**
-   **`total_violations`**: Sum of all events in `ViolationEvent`.
-   **`critical_violations`**: Count of events where `is_critical=True`.
-   **`heartbeat_integrity`**: Percentage of expected heartbeats received (detects gaps).

---

## 4. Deep-Dive: Integrity Audit Dashboard API

We will add a dedicated endpoint under `vmlc/` for exhaustive investigation.

### Endpoint: `GET /v2/exams/{exam_id}/candidates/{candidate_id}/integrity-audit/`

**Returns a chronologically ordered timeline of the exam attempt:**

```json
{
  "candidate": { "id": "uuid", "name": "John Doe" },
  "attempt_summary": {
    "started_at": "...",
    "submitted_at": "...",
    "total_duration": "55m"
  },
  "timeline": [
    {
      "type": "heartbeat",
      "timestamp": "2026-03-14T10:05:00Z",
      "sequence_number": 1,
      "face_capture_url": "https://s3.vmlc/heartbeats/uuid.jpg",
      "suspicion_score": 0.05,
      "events": []
    },
    {
      "type": "heartbeat",
      "timestamp": "2026-03-14T10:10:00Z",
      "sequence_number": 2,
      "face_capture_url": "https://s3.vmlc/heartbeats/uuid_2.jpg",
      "suspicion_score": 0.85,
      "events": [
        {
          "type": "TAB_SWITCH",
          "timestamp": "2026-03-14T10:07:15Z",
          "metadata": { "duration_seconds": 45 }
        }
      ]
    },
    {
      "type": "telemetry_gap",
      "expected_sequence": 3,
      "detected_at": "2026-03-14T10:15:00Z",
      "duration_seconds": 300,
      "message": "Missing heartbeat detected between Seq 2 and Seq 4"
    }
  ]
}
```

---

## 5. UI Client Implementation Recommendation

1.  **The "Integrity Badge":** In the `RankingSnapshot` table, color-code candidates by `proctoring_status`.
2.  **The "Time-Lapse" Player:** In the Audit Dashboard, allow admins to "play" the `face_capture` images as a slideshow, synchronized with the `events` timeline.
3.  **Review Action:** Add buttons in the Dashboard for admins to manually change the `proctoring_status` (e.g., from `suspicious` to `flagged` or `clear`) after review.
