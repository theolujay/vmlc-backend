# API Schema: Statistics & Summaries

This document outlines the schemas for endpoints providing statistical overviews and summarized data.

---

## 1. Overall Statistics
**Endpoint:** `GET /stats/overview/`

### Description
Retrieves system-wide statistics for candidates, staff, exams, competitions, helpdesk, and geographic distribution.
**Permission:** `ActiveVolunteerPermissions` (Moderator+)

### Response Schema
```json
{
  "candidates": {
    "registered": "number",
    "active": "number",
    "inactive": "number",
    "has_logged_in": "number",
    "pre_registered": "number",
    "deactivated": "number",
    "both_entities": "number"
  },
  "staff": {
    "registered": "number",
    "active": "number",
    "inactive": "number",
    "has_logged_in": "number",
    "pre_registered": "number",
    "deactivated": "number",
    "both_entities": "number"
  },
  "exams": {
    "total": "number",
    "active": "number",
    "ongoing": "number",
    "upcoming": "number",
    "concluded": "number",
    "drafts": "number"
  },
  "competition": {
    "active_competition": "string",
    "active_competition_id": "uuid",
    "stages": [
      {
        "id": "uuid",
        "name": "string",
        "type": "string",
        "rounds": ["number"]
      }
    ]
  },
  "helpdesk": {
    "total_threads": "number",
    "open_threads": "number",
    "in_progress_threads": "number",
    "resolved_threads": "number",
    "unassigned_threads": "number",
    "unread_messages": "number",
    "public_requests": "number"
  },
  "funnel": {
    "overall": { "pre_registrations": "number", "completed_registrations": "number", "conversion_percentage": "float" },
    "candidate": { "pre_registrations": "number", "completed_registrations": "number", "conversion_percentage": "float" },
    "volunteer": { "pre_registrations": "number", "completed_registrations": "number", "conversion_percentage": "float" }
  },
  "geographics": {
    "overall": [{ "state": "string", "count": "number" }],
    "candidate": [{ "state": "string", "count": "number" }],
    "volunteer": [{ "state": "string", "count": "number" }]
  }
}
```

---

## 2. Staff Helpdesk Thread List
**Endpoint:** `GET /staff/helpdesk/threads/`

### Description
Retrieves a paginated list of all helpdesk threads for staff, including a real-time summary of helpdesk statistics.
**Permission:** `ActiveModeratorPermissions` (Moderator+)

### Response Schema
```json
{
  "count": "number",
  "next": "string or null",
  "previous": "string or null",
  "helpdesk_summary_data": {
    "total_threads": "number",
    "open_threads": "number",
    "in_progress_threads": "number",
    "resolved_threads": "number",
    "unassigned_threads": "number",
    "unread_messages": "number",
    "public_requests": "number"
  },
  "results": [
    {
      "id": "uuid",
      "candidate_email": "string",
      "candidate_name": "string",
      "assigned_staff": "uuid or null",
      "assigned_staff_name": "string or null",
      "status": "string",
      "priority": "string",
      "last_message_at": "iso-datetime",
      "unread_by_staff_count": "number",
      "candidate_last_msg_preview": "string",
      "is_online": "boolean",
      "created_at": "iso-datetime"
    }
  ]
}
```

### Detailed Field Descriptions (Helpdesk List)

#### `helpdesk_summary_data`
- Same structure as the `helpdesk` field in `/stats/overview/`. Provides instant context for the support desk workload.

#### `results` (Thread Object)
- `unread_by_staff_count`: Count of messages sent by the candidate that have not yet been read by any staff member.
- `candidate_last_msg_preview`: A 100-character snippet of the latest message from the candidate.
- `is_online`: Boolean indicating if the candidate is currently active/online (via Redis cache).
- `assigned_staff_name`: Display name of the staff member currently assigned to the thread.
