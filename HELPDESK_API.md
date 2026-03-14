# Helpdesk API Documentation

The Helpdesk system facilitates authenticated communication between candidates and staff members. This document outlines the available endpoints, status transition logic, and automated features.

## Data Models

### HelpdeskThread
- **status**: `open`, `in_progress`, `closed`, `snoozed` (Default: `open`)
- **priority**: `low`, `medium`, `high` (Default: `medium`)
- **snoozed_until**: DateTime when the thread should automatically re-open (if status is `snoozed`).

### ThreadMessage
- **sender_type**: `candidate`, `staff`, `system`
- **text**: Message content.

---

## Endpoints

### 1. Get/Create Candidate Thread
**GET** `/v1/comms/helpdesk/thread/`  
*Permission: Authenticated User (Candidate)*

- **Behavior**: Retrieves the unique thread for the authenticated candidate. If no thread exists, it creates one and sends a system welcome message.
- **Side Effect**: Marks all staff messages in the thread as read. If the thread was `open`, it transitions to `in_progress`.

### 2. Send Message
**POST** `/v1/comms/helpdesk/thread/{thread_id}/message/`  
*Permission: Authenticated User (Owner or Moderator+)*

- **Request Body**:
  ```json
  {
    "text": "Hello, I need help with my exam."
  }
  ```
- **Status Transitions**:
    - **Candidate Message**:
        - If `snoozed` and `snoozed_until` is in the future: Status remains `snoozed`.
        - Otherwise: Status transitions to `open`.
    - **Staff/System Message**: Status transitions to `in_progress`.
- **Side Effect**: Broadcasts the message via WebSocket to `helpdesk_thread_{thread_id}`. Triggers escalation checks if sent by a candidate during an ongoing exam.

### 3. List Threads (Staff)
**GET** `/v1/comms/staff/helpdesk/threads/`  
*Permission: Active Moderator+*

- **Behavior**: Lists all threads containing at least one candidate message, ordered by unread count and activity.
- **Includes**: Real-time helpdesk stats (total open, unread, etc.).

### 4. Thread Detail (Staff)
**GET** `/v1/comms/staff/helpdesk/threads/{id}/`  
*Permission: Active Moderator+*

- **Side Effect**: Marks all candidate messages in the thread as read. Auto-reverts `snoozed` status to `closed` if `snoozed_until` has passed.

### 5. Thread Action (Staff)
**PATCH** `/v1/comms/staff/helpdesk/threads/{id}/action`  
*Permission: Active Admin+*

- **Request Body (Close)**:
  ```json
  {
    "status": "closed"
  }
  ```
- **Request Body (Snooze)**:
  ```json
  {
    "status": "snoozed",
    "snoozed_until": "2026-03-14T10:00:00Z"
  }
  ```
- **Validation**: `snoozed_until` is mandatory when status is `snoozed`.

---

## Automated Features

### 1. Helpdesk Escalation
If a candidate sends a message during an ongoing exam and no staff member replies within **2 minutes**, the system:
1.  Sends a Slack alert to the support channel.
2.  Notifies Admins and Managers via Email, Platform, and SMS.

### 2. Snooze Cleanup
A periodic task runs every **5 minutes** to identify threads in `snoozed` status where `snoozed_until` has passed. These threads are automatically transitioned to `closed`.

### 3. Real-time Updates
All thread activity (messages, status updates) is broadcasted via Django Channels to both the candidate and staff dashboards for real-time UI updates.

---

## WebSocket API

### UnifiedConsumer
**Endpoint**: `ws://host/ws/comms/`  
**Authentication**: JWT or API Key required

#### Actions

##### list_threads
Retrieves the list of helpdesk threads for staff dashboard.

- **Payload**:
  ```json
  {
    "action": "list_threads",
    "data": {
      "filters": {
        "search": "string",
        "status": "open" | "in_progress" | "closed" | "snoozed" | "default" | "all",
        "priority": "low" | "medium" | "high",
        "unread": "true" | "false",
        "sort": "string (e.g., -last_message_at, -priority)"
      },
      "request_id": 1
    }
  }
  ```

- **Filter Values**:
  - `status` accepts specific values or special keywords:
    - Specific: `open`, `in_progress`, `closed`, `snoozed`
    - `default`: Shows only `open` and `in_progress` threads (excludes `closed` and `snoozed`) - **applied automatically when at least one exam is ongoing**
    - `all`: Shows all threads regardless of status - **applied automatically when no exams are ongoing**
  - Other filters:
    - `search`: Partial match on candidate's name or email
    - `priority`: Exact match on thread priority
    - `unread`: Set to `"true"` to filter threads with unread messages
    - `sort`: Field to sort by (e.g., `last_message_at`, `-priority`). Defaults to `-unread_cnt, -last_message_at`
  - `request_id`: Optional integer to identify the request. Will be echoed back in the response.

- **Response**:
  ```json
  {
    "type": "helpdesk.list",
    "data": {
      "results": [...],
      "helpdesk_summary_data": {...},
      "filters": {
        "status": "open"
      },
      "request_id": 1
    }
  }
  ```

- **Notes**:
  - The `filters` field in the response echoes back the applied filters (including auto-computed `default` or `all` if not specified by client).
  - The `request_id` field in the response matches the client's request_id for request-response matching.

- **Auto-Filter Behavior**: When the WebSocket connects or a `list_threads` action is received without a status filter, the system automatically applies:
  - `default` filter (OPEN + IN_PROGRESS) if any exam is currently ongoing
  - `all` filter (all statuses) if no exams are ongoing

##### subscribe_thread
Subscribes to updates for a specific thread.

- **Payload**:
  ```json
  {
    "action": "subscribe_thread",
    "data": {
      "thread_id": "uuid"
    }
  }
  ```

##### unsubscribe_thread
Unsubscribes from a specific thread.

- **Payload**:
  ```json
  {
    "action": "unsubscribe_thread",
    "data": {
      "thread_id": "uuid"
    }
  }
  ```

##### thread.typing
Sends typing indicator to other participants in a thread.

- **Payload**:
  ```json
  {
    "action": "thread.typing",
    "data": {
      "thread_id": "uuid",
      "is_typing": true
    }
  }
  ```
