# Helpdesk WebSocket Documentation

The VMLC Helpdesk uses a **Unified WebSocket Consumer** to handle real-time notifications, thread dashboard updates, and per-thread communication (including typing indicators and presence).

## Endpoint
- **URL**: `ws://<host>/v1/ws/`
- **Authentication**: Requires both `Fully Authenticated` scope (JWT) and a valid `API Key`.

---

## 1. Client Actions (Client -> Server)

Clients interact with the helpdesk by sending JSON payloads with an `action` and optional `data`.

### Subscribe to a Thread
Used to receive real-time updates for a specific conversation.
```json
{
  "action": "subscribe_thread",
  "data": { "thread_id": "UUID" }
}
```

### Unsubscribe from a Thread
```json
{
  "action": "unsubscribe_thread",
  "data": { "thread_id": "UUID" }
}
```

### List Threads (Staff Only)
Used to manually fetch or filter the dashboard list.
```json
{
  "action": "list_threads",
  "data": {
    "filters": {
      "status": "open",
      "search": "candidate@example.com"
    }
  }
}
```

### Typing Indicator
Notify other participants that you are typing.
```json
{
  "action": "thread.typing",
  "data": {
    "thread_id": "UUID",
    "is_typing": true
  }
}
```

---

## 2. Server Events (Server -> Client)

All server events are returned in a consistent format: `{"type": "event_name", "data": { ... }}`.

### Thread List Update (`helpdesk.list`)
Sent to staff members upon connection or when a `list_threads` action is received.
```json
{
  "type": "helpdesk.list",
  "data": {
    "results": [
      {
        "id": "UUID",
        "candidate_email": "...",
        "status": "open",
        "unread_cnt": 2,
        "last_message_at": "..."
      }
    ],
    "helpdesk_summary_data": {
      "total_threads": 10,
      "total_unread": 5,
      "total_open": 3,
      "total_in_progress": 2,
      "total_closed": 4,
      "total_snoozed": 1
    }
  }
}
```

### Dashboard Heartbeat (`helpdesk.update`)
Sent to the `staff_helpdesk_dashboard` group when global state changes.
```json
{
  "type": "helpdesk.update",
  "data": {
    "stats": {
      "total_open": 5,
      "total_unread": 2
    },
    "refresh_threads": true
  }
}
```
*Note: If `refresh_threads` is true, the client should re-fetch or the consumer will automatically push a new `helpdesk.list`.*

### Thread Activity (`helpdesk.thread`)
Sent when a new message is posted or thread metadata (status, priority) changes.
```json
{
  "type": "helpdesk.thread",
  "data": {
    "thread_id": "UUID",
    "update_type": "message",
    "message": {
      "id": 1,
      "sender_type": "candidate",
      "text": "Hello!",
      "created_at": "..."
    },
    "thread": {
      "id": "UUID",
      "status": "in_progress",
      "assigned_staff": "UUID"
    }
  }
}
```

### Typing Notification (`helpdesk.thread.typing`)
Broadcasted to all participants of a thread *except* the sender.
```json
{
  "type": "helpdesk.thread.typing",
  "data": {
    "thread_id": "UUID",
    "user_id": "UUID",
    "is_typing": true
  }
}
```

---

## 3. Core Behaviors

### Presence & Online Status
- **Heartbeat**: Upon connection, a user's presence is registered in a Redis Sorted Set (`online_candidates` or `online_staff`).
- **Auto-Refresh**: The server runs a background task for each connection that refreshes this heartbeat every 30 seconds.
- **Expiration**: If a connection is lost, the heartbeat expires after 60 seconds, and the user is marked offline.

### Automatic List Refresh
The staff dashboard list is automatically refreshed (via `helpdesk.update`) when:
- A new message is received in *any* thread.
- A thread is closed or snoozed.
- A snooze period expires (via periodic cleanup task).

### Thread Scoping
- **Candidates**: Can only subscribe to their own thread.
- **Staff**: Can subscribe to any thread.
- **Typing Isolation**: Typing indicators are only received by users who have explicitly called `subscribe_thread` for that specific ID.
