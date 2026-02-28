# Unified WebSocket API Specification

This document provides a detailed technical reference for the VMLC Unified WebSocket API. All real-time functionality (Notifications, Presence, and Helpdesk) is consolidated into a single persistent connection.

## 1. Connection Details

- **URL:** `ws://<host>/v1/ws/`
- **Protocol:** JSON-based messages.
- **Handshake Requirements:**
    - `x-api-key`: Valid system API key.
    - `Authorization`: Bearer `<JWT_ACCESS_TOKEN>`.

### Connection Lifecycle
1.  **Authentication**: Handshake validated against API key and JWT.
2.  **Close Code 4003**: Sent if authentication fails or user is inactive.
3.  **Automatic Subscriptions**:
    - `user__<id>`: Private notification stream.
    - `staff_helpdesk_dashboard`: Global helpdesk updates (Moderators only).
4.  **Initial Payload**: Staff users receive an immediate `helpdesk.update` and `helpdesk.list` upon connection.
5.  **Presence**: User is marked "Online" in Redis. A background task refreshes this every 30 seconds.

---

## 2. Client-to-Server Actions

All messages sent to the server must follow this structure:
```json
{
  "action": "action_name",
  "data": { ... }
}
```

### `mark_notification_as_read`
Marks a specific notification as read.
- **Payload:**
    - `notification_id` (Integer): Required.

### `list_threads` (Staff Only)
Requests a paginated and/or filtered list of helpdesk threads.
- **Payload:**
    - `page` (Integer): Defaults to 1.
    - `filters` (Object): Optional.
        - `status` (String): `open`, `in_progress`, `resolved`.
        - `priority` (String): `low`, `medium`, `high`.
        - `search` (String): Partial match on name/email.
        - `unread` (Boolean): Filter for threads with unread messages.
        - `sort` (String): e.g., `-last_message_at`, `priority`.

### `subscribe_thread`
Join a specific chat room. Required to receive `helpdesk.thread` and `helpdesk.thread.typing` events for that thread.
- **Payload:**
    - `thread_id` (UUID String): Required.

### `unsubscribe_thread`
Leave a specific chat room.
- **Payload:**
    - `thread_id` (UUID String): Required.

### `thread.typing`
Broadcasts typing status to other participants in a subscribed thread.
- **Payload:**
    - `thread_id` (UUID String): Required.
    - `is_typing` (Boolean): Required.

---

## 3. Server to Client (Events)

All messages received from the server follow this structure:
```json
{
  "type": "event_type",
  "data": { ... } // Or flattened fields depending on event
}
```

### `notification_activity`
Real-time notification delivery.
- **Structure:**
```json
{
  "type": "notification_activity",
  "id": 123,
  "subject": "Exam Started",
  "message": "The Screening Exam is now live.",
  "type": "info", // alert, success, warning, error
  "link": "/exams/1",
  "is_read": false,
  "created_at": "ISO-8601-Timestamp"
}
```

### `helpdesk.update` (Staff Only)
Global helpdesk metrics. Sent when any thread state changes.
- **Data Object:**
    - `stats`:
        - `total_threads`: Total unique threads.
        - `open_threads`: Threads with 'open' status.
        - `in_progress_threads`: Threads with 'in_progress' status.
        - `resolved_threads`: Threads with 'resolved' status.
        - `unassigned_threads`: Threads with no assigned staff.
        - `unattended_candidates`: Threads that have at least one candidate message unread by staff.
        - `unread_messages`: Total count of candidate messages unread by staff.
        - `online_candidates`: Count of candidates currently connected via WebSocket.
        - `online_staff`: Count of staff currently connected via WebSocket.
    - `refresh_threads` (Boolean): If `true`, the client should expect a `helpdesk.list` follow-up or trigger a refresh.

### `helpdesk.list` (Staff Only)
The serialized thread list for the dashboard.
- **Data Object:**
    - `results` (Array): List of thread objects.
        - `id`: UUID.
        - `candidate_name`: String.
        - `candidate_email`: String.
        - `assigned_staff_name`: String or null.
        - `status`: String.
        - `priority`: String.
        - `last_message_at`: Timestamp.
        - `unread_by_staff_count`: Integer.
        - `candidate_last_msg_preview`: String (max 100 chars).
        - `is_candidate_online`: Boolean (candidate presence).
        - `last_message_sender_type`: `candidate` or `staff`.
        - `is_unattended`: Boolean.
    - `pagination`:
        - `count`: Total results.
        - `page`: Current page.
        - `page_size`: Results per page.
        - `total_pages`: Total pages.
        - `has_next`: Boolean.
        - `has_previous`: Boolean.

### `helpdesk.thread`
A new message or metadata update in a subscribed thread.
- **Data Object:**
    - `thread_id`: UUID.
    - `update_type`: `"message"` or `"metadata"`.
    - `message`: (Optional) The new message object if `update_type` is `"message"`.
    - `thread`: Minimal thread metadata (status, priority, assigned_staff, last_message_at, is_candidate_online).

### `helpdesk.thread.typing`
Typing status from another user in a thread.
- **Payload:**
```json
{
  "type": "helpdesk.thread.typing",
  "thread_id": "UUID",
  "user_id": "UUID",
  "is_typing": true
}
```

---

## Error Handling

Generic error message format:
```json
{
  "type": "error",
  "message": "Human readable error description"
}
```
**Common Errors:**
- `Unknown action: <name>`: Sent when an invalid action is requested.
- `Thread access denied`: Sent if a user tries to subscribe to a thread they don't own (and aren't staff).
- `Permission denied`: Sent if a candidate tries to call `list_threads`.
