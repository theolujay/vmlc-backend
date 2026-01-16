# `comms` Application

The `comms` Django application is responsible for managing all communication functionalities within the VMLC backend, including broadcasting messages, sending notifications, handling real-time updates via WebSockets, and logging communication activities. It integrates with Celery for asynchronous task processing and Twilio for SMS/WhatsApp messaging.

## Key Modules and Their Responsibilities

-   **`admin.py`**: Configures the Django Admin interface for `Broadcast`, `BroadcastLog`, `Notification`, and `BackupLog` models. It provides custom displays for monitoring broadcast task statuses and results.
-   **`apps.py`**: Django application configuration for `comms`.
-   **`consumers.py`**: Contains the `NotificationConsumer`, an asynchronous WebSocket consumer that manages real-time notifications for users. It handles WebSocket connections, disconnections, and enables users to mark notifications as read.
-   **`functions.py`**: Houses the core logic for sending various types of messages.
    -   `send_broadcast`: Orchestrates the process of sending mass messages (email, SMS, platform notifications) to target user roles (staff or candidates) using Celery tasks.
    -   `_send_sms_broadcast`, `_send_email_broadcast`, `_send_platform_broadcast`: Helper functions that encapsulate the specific logic for sending messages via different mediums.
-   **`middleware.py`**: Implements `DualAuthMiddleware` for WebSocket connections, ensuring that both an API key and a JWT token are present and valid for authentication.
-   **`models.py`**: Defines the database schemas for communication-related data:
    -   `Broadcast`: Represents a mass message intended for multiple recipients, specifying subject, message content, communication mediums (platform, email, WhatsApp, SMS), and target user roles.
    -   `BroadcastLog`: Records the outcome of each individual message attempt within a broadcast, including medium, target role, status (pending, sent, failed), and any associated messages.
    -   `Notification`: Stores individual real-time notifications destined for a specific user, tracking subject, message, and read status.
    -   `BackupLog`: Stores logs related to database backup operations.
-   **`routing.py`**: Defines the URL routing for WebSocket connections, mapping `/v1/ws/notifications/` to the `NotificationConsumer`.
-   **`serializers.py`**: Provides Django REST Framework serializers for `Broadcast` (list and detail views), `BroadcastLog`, and `Notification` models, facilitating data serialization and deserialization for API interactions.
-   **`signals.py`**: Connects Celery task success and failure signals to handle post-task logic, such as alerting administrators about low broadcast success rates via email. It also defines a `notifications_created` signal for custom listeners.
-   **`tasks.py`**: Contains Celery tasks for asynchronous execution of communication operations, notably `send_broadcast_task`, which delegates to `comms.functions.send_broadcast`.
-   **`urls.py`**: Maps API endpoints related to broadcast management (`/broadcasts/`) and a webhook for database backup status (`/webhooks/db-backup/`).
-   **`utils.py`**: Contains utility functions for interacting with external communication services:
    -   `send_phone_msg`, `send_bulk_phone_msg`: Functions for sending single and bulk SMS/WhatsApp messages using the Twilio API.
    -   `send_backup_status_to_slack`: Integrates with Slack to send notifications regarding database backup statuses.

## Interconnections

-   **`vmlc.models`**: The `comms` app extensively uses `vmlc.models.Staff` and `vmlc.models.Candidate` to identify and target users for broadcasts and notifications. The `User` model from `vmlc.models` is the recipient of `Notification` objects.
-   **`vmlc.utils.exceptions`**: Custom exceptions defined in the `vmlc` app are used for error handling within `comms.functions`.
-   **`vmlc.tasks`**: Celery tasks are defined in `comms.tasks` and integrated into `comms.functions` and `comms.signals` for asynchronous processing and monitoring.
-   **Channels**: The `comms` app leverages `channels` for WebSocket communication, utilizing `channels.layers` for real-time notification delivery.
-   **Celery**: Critical communication tasks like `send_broadcast` are executed asynchronously via Celery, ensuring non-blocking operations.
-   **Twilio**: Used by `comms.utils` for sending SMS and WhatsApp messages.
-   **Slack**: Integrated via `comms.utils` to send notifications about database backup events.
-   **Django Cache**: Used for caching broadcast details and other data to improve performance.

The `comms` application is a central hub for various communication streams, ensuring timely and targeted delivery of information within the VMLC ecosystem, with robust error handling and asynchronous processing capabilities.