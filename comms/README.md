# `comms` Application

The `comms` application is the central communication hub of the VMLC backend. It manages mass broadcasts, real-time user notifications, helpdesk chat threading, and system alerts. It leverages Celery for asynchronous processing and WebSockets for live updates.

## Key Modules and Their Responsibilities

-   **`services/`**: Houses the core business logic for communication, decoupled from Django models and views.
    -   `notification.py`: Orchestrates notifications across multiple mediums (Platform, Email, SMS, WhatsApp) and manages the `send_broadcast` lifecycle.
    -   `email.py`: Handles email template building for registrations, support inquiries, and system alerts.
    -   `kudi_sms.py`: Integration with Kudi SMS API for bulk and transactional messaging.
    -   `slack.py`: Manages outbound Slack notifications for system events like backup status and low SMS balance alerts.
-   **`models.py`**: Defines the data structures for communication:
    -   `Broadcast`: Represents a mass message with targeted roles (Staff/Candidate) and mediums.
    -   `BroadcastLog`: Tracks the success/failure of each medium-role combination in a broadcast.
    -   `Notification`: Stores individual real-time alerts for specific users.
    -   `HelpdeskThread` & `ThreadMessage`: Powers the internal helpdesk system for tracking and responding to user inquiries.
    -   `PublicSupportRequest`: Captures public/anonymous inquiries from the landing page.
    -   `BackupLog`: Records the outcome of database backup operations.
-   **`consumers.py`**: Implements WebSocket consumers for real-time features.
    -   `NotificationConsumer`: Real-time delivery of notifications over WebSockets.
    -   `HelpdeskConsumer`: Real-time helpdesk chat, presence, and typing indicators.
-   **`tasks.py`**: Celery tasks for background processing:
    -   `send_broadcast_task`: Triggers the asynchronous broadcast engine.
    -   `send_mail_task` & `send_bulk_sms_task`: Generic tasks for sending individual or bulk messages.
    -   `notify_candidates_about_exam_task`: Handles automated exam reminders.
    -   `helpdesk_escalation_task`: Schedules alerts for unresponded helpdesk messages.
-   **`middleware.py`**: Provides `DualAuthMiddleware` for WebSocket connections, ensuring secure authentication via API Keys and JWT tokens.
-   **`routing.py`**: Maps WebSocket connections (e.g., `/v1/ws/notifications/`, `/v1/ws/helpdesk/thread/`) to consumers.
-   **`urls.py`**: Defines REST API endpoints for broadcast management, notification history, helpdesk, and backup webhooks.

## Architecture & Integration

### Asynchronous Execution
Critical or time-consuming operations (e.g., sending 1000+ emails/SMS) are offloaded to **Celery**. This ensures the API remains responsive while background workers handle the heavy lifting.

### Real-Time Updates
The `comms` app uses **Django Channels** to push notifications and chat messages directly to the user's dashboard.
-   **Notifications**: Broadcast to the user's specific WebSocket group (`user__<id>`).
-   **Helpdesk**: Broadcast to a shared thread group (`helpdesk_thread_<uuid>`).

### Helpdesk & Support
The application provides a two-tier support system:
1.  **Public Inquiries**: Captured via `PublicSupportRequest` from non-authenticated users.
2.  **Helpdesk**: Authenticated users and staff interact via `HelpdeskThread` and `ThreadMessage`, allowing for threaded, persistent, and real-time support history.

### External Services
-   **Kudi SMS**: Primary provider for SMS delivery in Nigeria. Includes balance monitoring and low-balance alerts.
-   **Twilio**: Backup provider for SMS and primary for WhatsApp messaging.
-   **Slack**: Used for internal engineering alerts (Backups, System Health, Support Escalation).
-   **Django Mail**: Used for transactional and mass email delivery.

## Interconnections

-   **`identity`**: Uses `User`, `Staff`, and `Candidate` models to resolve recipients and roles.
-   **`vmlc`**: Integrates with `Exam` and `Competition` logic to trigger automated event-based notifications.
-   **`vmlc.utils`**: Uses shared exceptions, security helpers, and X-API-Key validation.
