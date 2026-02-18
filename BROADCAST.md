# Broadcast & Notifications API Documentation

The Broadcast and Notifications API allows staff members to send mass messages across various communication channels and manage real-time platform notifications.

---

## 1. Broadcasts

Broadcasts are mass messages dispatched to specific user roles via Email, SMS, WhatsApp, and Platform Notifications.

### Endpoints Summary

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/v1/broadcasts/` | List all broadcasts (with pagination and summary) |
| `POST` | `/v1/broadcasts/` | Create and send (or schedule) a new broadcast |
| `GET` | `/v1/broadcasts/<int:broadcast_id>/` | Retrieve details of a specific broadcast |

### Create / Schedule Broadcast
`POST /v1/broadcasts/`

Creates a broadcast record and triggers the sending process. If `scheduled_at` is provided, the delivery is delayed until the specified time.

#### Permissions
- **Active Manager Permissions**: Requires the user to be an active staff member with at least a `manager` role.

#### Request Body
```json
{
  "subject": "System Maintenance",
  "message": "The platform will be down for maintenance on Sunday between 2:00 AM and 4:00 AM WAT.",
  "mediums": ["platform", "email", "sms"],
  "target_roles": {
    "staff": ["volunteer", "moderator"],
    "candidate": ["league", "final"]
  },
  "scheduled_at": "2026-02-20T02:00:00Z"
}
```

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `subject` | `string` | Yes | Title of the broadcast (max 100 characters). |
| `message` | `string` | Yes | The body of the message. |
| `mediums` | `array` | Yes | List of channels: `platform`, `email`, `whatsapp`, `sms`. |
| `target_roles` | `object` | Yes | Dictionary mapping user types (`staff`, `candidate`) to lists of roles. |
| `scheduled_at` | `string` | No | ISO 8601 timestamp for future delivery. |

#### Response (`201 Created`)
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
  "status": "pending",
  "mediums": ["platform", "email", "sms"],
  "target_roles": {
    "staff": ["volunteer", "moderator"],
    "candidate": ["league", "final"]
  },
  "scheduled_at": "2026-02-20T02:00:00Z",
  "created_at": "2026-02-18T12:00:00Z"
}
```

---

## 2. Platform Notifications

Notifications are real-time, in-platform messages delivered to specific users.

### Endpoints Summary

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/v1/notifications/` | List notifications for the authenticated user |
| `PATCH` | `/v1/notifications/<int:id>/mark-as-read/` | Mark a specific notification as read |
| `PATCH` | `/v1/notifications/mark-all-as-read/` | Mark all notifications as read |

### List Notifications
`GET /v1/notifications/`

Returns a paginated list of notifications for the current user, along with status statistics.

#### Query Parameters
| Parameter | Type | Description |
| :--- | :--- | :--- |
| `status` | `string` | Filter by `read` or `unread`. |

#### Response (`200 OK`)
```json
{
  "stats": {
    "total_count": 15,
    "unread_count": 3,
    "read_count": 12
  },
  "count": 15,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 120,
      "type": "info",
      "subject": "Welcome!",
      "message": "Welcome to the platform.",
      "is_read": false,
      "created_at": "2026-02-18T10:00:00Z"
    }
  ]
}
```

---

## 3. Support Chat

The system supports 1:1 chat between candidates and staff for technical or academic support.

### Endpoints Summary

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/v1/support/thread/` | Get or create support thread (Candidate) |
| `POST` | `/v1/support/thread/<uuid:id>/message/` | Send message to thread |
| `GET` | `/v1/staff/support/threads/` | List all support threads (Staff) |
| `GET` | `/v1/staff/support/threads/<uuid:id>/` | Retrieve specific thread (Staff) |

#### Escalation Logic
If a candidate sends a message and there is no staff reply within **2 minutes**, the system automatically escalates the thread:
- A Slack alert is sent to the `#support` channel.
- Email and SMS alerts are sent to all active Admins and Managers.

---

## 4. Behavioral & Implementation Details

### Asynchronous Processing
All broadcasts are handled via Celery.
- **Immediate Broadcasts**: Queued immediately upon creation.
- **Scheduled Broadcasts**: Queued with an `ETA` based on `scheduled_at`.
- **Bulk SMS**: Uses the **Kudi SMS** provider. Includes automatic balance checks and 1-hour retries if credit is insufficient.

### Real-time Delivery
- **Platform Notifications**: Dispatched via WebSockets (Django Channels) to the `user__<user_id>` group.
- **Support Chat**: Dispatched via WebSockets to the `support_thread_<thread_id>` group.

### Caching Strategy
- **Broadcast Summary**: Cached for 1 hour; invalidated on new broadcast creation.
- **Broadcast Detail**: Cached for 1 hour; invalidated upon completion of the background task.
- **Notifications**: Versioned caching is used for user notification lists. Caches are invalidated when notifications are marked as read.

### Broadcast Logs
Each broadcast creates `BroadcastLog` entries for every medium-role combination. This allows tracking the exact number of recipients reached per channel (e.g., "Successfully sent to 850 recipients via Email").
