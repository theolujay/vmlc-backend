# Broadcast API Documentation

The Broadcast API allows staff members with managerial permissions to send messages to multiple users across various communication channels (Email, SMS, WhatsApp, and Platform Notifications).

## Endpoints Summary

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/v1/broadcasts/` | Create and send a new broadcast |
| `GET` | `/v1/broadcasts/` | List all broadcasts (paginated) |
| `GET` | `/v1/broadcasts/<int:broadcast_id>/` | Retrieve details of a specific broadcast |

---

## Create Broadcast
`POST /v1/broadcasts/`

Creates a broadcast record and asynchronously triggers the sending process.

### Permissions
- **Active Manager Permissions**: Requires the user to be an active staff member with at least a `manager` role.

### Request Body
```json
{
  "subject": "System Maintenance",
  "message": "The platform will be down for maintenance on Sunday between 2:00 AM and 4:00 AM WAT.",
  "mediums": ["platform", "email", "sms"],
  "target_roles": {
    "staff": ["volunteer", "moderator"],
    "candidate": ["league", "final"]
  }
}
```

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `subject` | `string` | Yes | Title of the broadcast (max 100 characters). |
| `message` | `string` | Yes | The body of the message. |
| `mediums` | `array` | Yes | List of channels: `platform`, `email`, `whatsapp`, `sms`. |
| `target_roles` | `object` | Yes | Dictionary mapping user types to roles. Valid keys: `staff`, `candidate`. |

### Response (`201 Created`)
```json
{
  "id": 42,
  "subject": "System Maintenance",
  "message": "The platform will be down for maintenance...",
  "created_by": {
    "id": 1,
    "user": {
      "first_name": "Admin",
      "last_name": "User"
    }
  },
  "created_at": "2026-02-15T12:00:00Z",
  "mediums": ["platform", "email", "sms"],
  "target_roles": {
    "staff": ["volunteer", "moderator"],
    "candidate": ["league", "final"]
  },
  "status": "pending",
  "last_attempt": null,
  "logs": []
}
```

---

## List Broadcasts
`GET /v1/broadcasts/`

Returns a paginated list of all broadcasts with aggregate summary data.

### Query Parameters
| Parameter | Type | Description |
| :--- | :--- | :--- |
| `status` | `string` | Filter by status (e.g., `sent`, `pending`, `failed`, `partial`). |
| `medium` | `string` | Filter by medium (e.g., `email`, `sms`, `whatsapp`, `platform`). |
| `search` | `string` | Partial match search on subject or message content. |
| `created_at` | `string` | Filter by creation date (`YYYY-MM-DD`). |

### Response (`200 OK`)
```json
{
  "broadcast_summary_data": {
    "total_broadcasts": 42,
    "sent_count": 38,
    "pending_count": 1,
    "failed_count": 2,
    "partial_count": 1,
    "email_count": 40,
    "sms_count": 10,
    "whatsapp_count": 5,
    "platform_count": 42
  },
  "count": 42,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 42,
      "subject": "System Maintenance",
      "message": "The platform will be down for maintenance...",
      "created_by": { ... },
      "created_at": "2026-02-15T12:00:00Z",
      "mediums": ["platform", "email"],
      "target_roles": {
        "candidate": ["league"]
      }
    }
  ]
}
```

---

## Retrieve Broadcast Detail
`GET /v1/broadcasts/<int:broadcast_id>/`

Returns full details of a specific broadcast, including the status of each medium-role combination.

### Response (`200 OK`)
```json
{
  "id": 42,
  "subject": "System Maintenance",
  "message": "...",
  "status": "sent",
  "last_attempt": "2026-02-15T12:05:00Z",
  "logs": [
    {
      "id": 150,
      "medium": "email",
      "target_role": "league",
      "role_type": "candidate",
      "status": "sent",
      "message": "Successfully sent to 850 recipients",
      "attempted_at": "2026-02-15T12:05:00Z"
    },
    {
      "id": 151,
      "medium": "platform",
      "target_role": "league",
      "role_type": "candidate",
      "status": "sent",
      "message": "Successfully sent to 850 recipients",
      "attempted_at": "2026-02-15T12:05:05Z"
    }
  ]
}
```

---

## Behavioral Specifications

### 1. Asynchronous Execution
When a broadcast is created, the API returns immediately with a `201 Created` status. The actual delivery happens in the background via Celery. The broadcast status will transition from `pending` -> `in_progress` -> `sent` (or `partial` / `failed`).

### 2. Targeting Logic
- The system identifies all active users matching the specified roles.
- If multiple roles are selected, the broadcast is sent to the union of all matching users.
- For `platform` notifications, a `Notification` record is created for each recipient, and a real-time message is pushed via WebSockets (Django Channels).

### 3. Medium-Specific Logic
- **Email**: Uses `send_mass_mail` for efficient delivery.
- **SMS**: Sends through the configured SMS provider (e.g., Kudi).
- **WhatsApp**: (Current Implementation Note) WhatsApp delivery might require pre-approved templates depending on the provider configuration.
- **Platform**: Creates internal notifications visible in the candidate/staff dashboards.

### 4. Logging and Retries
- Every attempt to send a broadcast to a specific role-medium combination is logged in `BroadcastLog`.
- If an entire broadcast fails due to a retryable error (like a database connection issue), the Celery task will retry up to 3 times with a 60-second delay.

### 5. Caching
- Broadcast details are cached for 1 hour to reduce database load. 
- The cache for a specific broadcast is automatically invalidated once the background sending task completes.
