# SMS Notification System Mapping

This document maps the architecture and flow of the SMS notification system within the `comms` app.

## 1. Overview
The SMS system is designed to deliver concise, actionable messages to users (Candidates and Staff). It handles single notifications, mass broadcasts, and automated exam-related alerts, with intelligent condensing to stay within SMS character limits (160 characters).

## 2. Core Components

### Utilities (`comms/utils.py`)
- **`format_sms_body(subject, message)`**: The central formatting engine. It:
  - Strips redundant whitespace/newlines.
  - Combines subject and message (e.g., "Subject: Message").
  - Intelligently truncates the message while preserving the subject if possible.
- **`_normalize_phone(phone)`**: Converts local Nigerian numbers (080...) to E.164 format (234...).
- **`is_placeholder_phone(phone)`**: Filters out test numbers to prevent wasted credits.

### Models (`comms/models.py`)
- **`Broadcast`**: Stores mass message metadata.
  - `sms_message`: An optional field allowing admins to provide a hand-crafted, short SMS version of a longer broadcast.
- **`BroadcastLog`**: Tracks delivery status per medium/role.

### Services (`comms/services/`)
- **`NotificationService`**: Orchestrates the dispatch.
- **`KudiSmsService`**: Integration with the Kudi SMS gateway API.

---

## 3. Workflows

### A. Single User Notification (`notify_user`)
Used for ad-hoc alerts or transactional messages.
1.  **Trigger**: Call `notify_user(user, subject, message, mediums=['sms'])`.
2.  **Formatting**: Calls `format_sms_body(subject, message)`.
3.  **Normalization**: Normalizes the recipient's phone number.
4.  **Dispatch**: Calls `_send_via_sms` (Synchronous).

### B. Mass Broadcasts (`send_broadcast`)
Used by staff to send announcements to specific roles.
1.  **Trigger**: Triggered via API or Admin.
2.  **Content Selection**:
    - If `broadcast.sms_message` is provided, it is used directly.
    - Otherwise, `format_sms_body` generates a version from the main message.
3.  **Task Queuing**: `_send_sms_broadcast` calls `send_bulk_phone_msg`.
4.  **Background Processing**: If using Kudi, it triggers `send_bulk_sms_task` (Celery).
    - Checks balance and estimates cost.
    - Dispatches to Kudi in bulk.

### C. Automated Exam Alerts (`notify_candidates_about_exam`)
Triggered by exam lifecycle events (Scheduled, Reminder, Started).
1.  **Template Generation**: `_build_exam_notification_content` returns an `sms_template` (pre-optimized for length).
2.  **Personalization**: Formats the template with candidate names and exam details.
3.  **Grouped Dispatch**: If multiple candidates share a phone number (e.g., siblings), names are combined (e.g., "Alice and Bob") to send a single SMS.
4.  **Dispatch**: Calls `notify_user` with the optimized message.

---

## 4. Message Condensing Logic

The system follows a hierarchy for SMS content:
1.  **Explicit SMS Content**: Highest priority (from `Broadcast.sms_message`).
2.  **Dedicated SMS Template**: Medium priority (from `_build_exam_notification_content`).
3.  **Automatic Condensing**: Fallback (via `format_sms_body`).

### `format_sms_body` Strategy:
- **Length <= 160**: Full content used.
- **Length > 160**:
  - If a subject exists: `Subject: [Truncated Message]...`
  - No subject: `[Truncated Message]...`

---

## 5. Service Providers
- **Primary (Kudi SMS)**: Used for bulk delivery in Nigeria. Supports balance checks and async task retries.
- **Secondary (Twilio)**: Used primarily for WhatsApp and as a fallback for SMS in specific environments (e.g., tests).

---

## 6. Exam Transition Notification Flows

This section details exactly what happens when an exam moves through its lifecycle.

### A. Draft -> Scheduled
**Trigger**: A staff member updates an exam's `scheduled_date` and `countdown_minutes` (usually via `ExamDetailV2View`).

1.  **Database Save**: The `Exam.save()` method is called.
2.  **Signal Triggered**: A `post_save` signal for the `Exam` model is dispatched.
3.  **Invalidation & Task Queue**: `vmlc.signals.invalidate_dashboard_on_change` is triggered. Since it's a significant update (or creation), it:
    -   Queues `invalidate_exam_related_caches_task` to clear dashboards.
    -   Queues `notify_candidates_about_exam_task(exam_id, "scheduled")`.
4.  **Notification Dispatch**:
    -   The task initializes `NotificationService`.
    -   It identifies all candidates enrolled in the exam's competition stage.
    -   **Email**: Sends the full "New Exam Scheduled" email.
    -   **SMS**: Uses `format_sms_body` (or a dedicated template) to send: *"Hi [Name], new exam '[Title]' scheduled for [Date]. Log in for details. -VMLC Team"*.

### B. Scheduled -> Ongoing (The "Start" Transition)
**Trigger**: The current time reaches the `scheduled_date`. This is detected by the periodic `check_exam_status_transitions_task` (runs every ~1-5 minutes).

1.  **Status Check**: The task identifies exams where `last_run < scheduled_date <= now`.
2.  **Notification Trigger**: The task calls `notify_candidates_about_exam_task(exam_id, "started")`.
3.  **Notification Dispatch**:
    -   **Email**: Sends "Exam Started" email.
    -   **SMS**: Sends: *"Exam '[Title]' has started! It closes at [Time]. Good luck! -VMLC Team"*.
4.  **Cache Invalidation**: `invalidate_exam_related_caches_task` is triggered to update candidate dashboards to show the "Take Exam" button.

### C. Ongoing -> Concluded
**Trigger**: The current time reaches `scheduled_date + open_duration_hours`. Detected by `check_exam_status_transitions_task`.

1.  **Status Check**: The task identifies exams where `last_run < conclusion_time <= now`.
2.  **Cache Invalidation**: `invalidate_exam_related_caches_task` is triggered.
3.  **Dashboard Update**: The candidate dashboard transitions from "Take Exam" to "Concluded" or "Result Pending".
4.  **Note**: Currently, there is no automated SMS/Email sent *immediately* upon conclusion to avoid spamming, but the system invalidates caches to ensure the UI reflects the state change.

### D. Special Transition: 1-Hour Reminder
**Trigger**: One hour before `scheduled_date`. Detected by `check_exam_status_transitions_task`.

1.  **Detection**: Task finds exams where `last_run < (scheduled_date - 1 hour) <= now`.
2.  **Notification Trigger**: Calls `notify_candidates_about_exam_task(exam_id, "reminder")`.
3.  **Notification Dispatch**:
    -   **Email**: Sends "Exam Reminder" email.
    -   **SMS**: Sends: *"Reminder: Your exam '[Title]' starts in 1 hour ([Time]). Get ready! -VMLC Team"*.
