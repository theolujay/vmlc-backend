# Helpdesk API Specification

This document defines the REST API and WebSocket behavior for the real-time in-app helpdesk system.

## 1. REST API Endpoints

### A. Get or Create Helpdesk Thread (Candidate)
**Endpoint:** `GET /v1/helpdesk/thread/`
**Permission:** Candidate only.

**Behavior:**
- If a thread exists for the authenticated candidate, it returns the existing thread.
- If not, it creates a new thread.
- Upon creation, a system message is automatically inserted: `"Hello, {full_name}. How can we help you today?"`
- Marks all unread messages as read for the candidate.

**Response Body (200 OK):**
```json
{
    "id": "uuid-string",
    "candidate_name": "John Doe",
    "candidate_email": "john.doe@example.com",
    "candidate_phone": "2348012345678",
    "assigned_staff": null,
    "assigned_staff_name": null,
    "participating_staff_names": [],
    "status": "open",
    "priority": "medium",
    "last_message_at": "2023-10-27T10:00:00Z",
    "messages": [
        {
            "id": 1,
            "sender": null,
            "sender_name": "System",
            "sender_type": "system",
            "text": "Hello, John Doe. How can we help you today?",
            "metadata": null,
            "is_read": true,
            "created_at": "2023-10-27T10:00:00Z"
        }
    ],
    "created_at": "2023-10-27T10:00:00Z",
    "updated_at": "2023-10-27T10:00:00Z"
}
```

---

### B. Post Message
**Endpoint:** `POST /v1/helpdesk/thread/{thread_id}/message/`
**Permission:** Authenticated User (Thread owner or Staff (Moderator+)).

**Behavior:**
- Validates that the sender is either the candidate who owns the thread or a staff member with at least a **Moderator** role.
- Saves the `ThreadMessage`.
- Automatically updates `thread.last_message_at`.
- **WebSocket Broadcast:** Sends a `chat.message` event to the group `helpdesk_thread_{thread_id}`.
- **Staff Load Balancing:** If this is the first staff reply to an unassigned thread, it automatically assigns the thread to the active staff member with the lowest load and updates status to `in_progress`.
- **Escalation:** If the sender is a candidate, schedules a Celery task to check for escalation in 2 minutes.

**Request Body:**
```json
{
    "text": "I need help with my exam login.",
    "metadata": {
        "exam_id": 123,
        "device": "Chrome/Linux"
    }
}
```

**Response Body (201 Created):**
```json
{
    "id": 45,
    "sender": "uuid-user-id",
    "sender_name": "John Doe",
    "sender_type": "candidate",
    "text": "I need help with my exam login.",
    "metadata": {
        "exam_id": 123,
        "device": "Chrome/Linux"
    },
    "is_read": true,
    "created_at": "2023-10-27T10:05:00Z"
}
```

---

### C. Staff Helpdesk Thread List
**Endpoint:** `GET /v1/staff/helpdesk/threads/`
**Permission:** Staff (Moderator+).

**Behavior:**
- Returns a list of all helpdesk threads.
- **Ordering:**
    1. Unread count (descending)
    2. Last message timestamp (descending)
- Includes candidate online status (fetched from Redis presence).

**Response Body (200 OK):**
```json
{
    "count": 1,
    "next": null,
    "previous": null,
    "results": [
        {
            "id": "uuid-string",
            "candidate_email": "john.doe@example.com",
            "candidate_name": "John Doe",
            "assigned_staff": 5,
            "assigned_staff_name": "Staff Member",
            "status": "in_progress",
            "priority": "medium",
            "last_message_at": "2023-10-27T10:05:00Z",
            "unread_by_staff_count": 2,
            "candidate_last_msg_preview": "I need help with my exam login...",
            "is_online": true,
            "created_at": "2023-10-27T10:00:00Z"
        }
    ]
}
```

---

### D. Staff Helpdesk Thread Detail
**Endpoint:** `GET /v1/staff/helpdesk/threads/{id}/`
**Permission:** Staff (Moderator+).

**Behavior:**
- Retrieves the full thread details and message history.
- Marks all unread messages as read for the authenticated staff user.

**Response Body (200 OK):**
Same as **Get or Create Helpdesk Thread (Candidate)**.

---

## 2. WebSocket Interface

**URL:** `ws://{host}/v1/ws/helpdesk/thread/{thread_id}/`

### Connection Behavior
- **Authentication:** Requires valid JWT or API Key (handled via `Channels` middleware).
- **Authorization:** Rejects connection if user is neither the thread owner nor staff with at least a **Moderator** role.
- **Presence:** Sets `user_online_{user_id} = 1` in Redis with 60s TTL on connect.
- **Keep-Alive:** Refreshes presence TTL every 30 seconds via a background task.

### Inbound Events (Client to Server)

#### Typing Indicator
```json
{
    "type": "chat.typing",
    "is_typing": true
}
```

### Outbound Events (Server to Client)

#### New Message
Sent when a message is posted via REST API.
```json
{
    "type": "chat.message",
    "message": {
        "id": 45,
        "sender": "uuid-user-id",
        "sender_name": "John Doe",
        "sender_type": "candidate",
        "text": "...",
        "metadata": {},
        "is_read": false,
        "created_at": "..."
    }
}
```

#### Typing Status
Broadcasted to all members in the thread group except the sender.
```json
{
    "type": "chat.typing",
    "user_id": "uuid-user-id",
    "is_typing": true
}
```

---

## 3. Background Behavior (Celery)

### Escalation Check (`support_escalation_task`)
- Scheduled 2 minutes after a candidate sends a message.
- Checks if the last message in the thread is still from the candidate.
- If so, triggers alerts (Email, SMS, Slack) to all active Admins, Managers, and Superadmins.

### Staff Load Balancing
- Triggered on the first staff reply to an unassigned thread.
- Automatically assigns the staff member with the lowest number of `in_progress` threads (among eligible support roles: Moderator, Admin, Manager, Superadmin) to the conversation.
