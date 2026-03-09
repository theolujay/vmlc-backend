# SMS Notification Report

This document outlines all locations and mechanisms for sending SMS notifications within the VMLC Backend.

## 1. Core Services

The SMS infrastructure is built around a two-tier service architecture.

### KudiSmsService (`comms/services/kudi_sms.py`)
This is the low-level provider service that interacts directly with the **Kudi SMS API**. It handles:
- **`send_bulk_sms`**: Sending standard messages to one or more recipients.
- **`send_personalised_sms`**: Sending custom messages for specific recipients.
- **`send_otp`**: Sending one-time passwords.
- **`get_balance`**: Checking the Kudi wallet balance.
- **`estimate_cost`**: Calculating the potential cost based on message length and recipient count.

### NotificationService (`comms/services/notification.py`)
The primary orchestration service that abstracts SMS delivery alongside Email and Platform notifications.
- **`notify_user`**: Sends a single SMS to a specific user if the `sms` medium is requested.
- **`send_broadcast`**: Orchestrates mass SMS delivery for the Broadcast system.
- **`send_phone_msg` / `send_bulk_phone_msg`**: High-level wrappers that route messages to the correct provider (Kudi for SMS, Twilio for WhatsApp) and handle asynchronous queuing via Celery.

---

## 2. Asynchronous Tasks (Celery)

To prevent API latency, all SMS operations are offloaded to Celery workers in the `comms` queue.

- **`send_bulk_sms_task` (`comms/tasks.py`)**: 
  - The main worker for SMS delivery.
  - Includes **automatic balance checks** before sending.
  - If the Kudi balance is insufficient, it triggers a **Slack alert** and retries every hour.
  - Updates `BroadcastLog` status once delivery is attempted.
- **`notify_user_task` (`comms/tasks.py`)**: 
  - Handles single-user notifications, including SMS if specified in the `mediums` list.

---

## 3. SMS Notification Triggers

SMS notifications are triggered by the following events:

### A. Broadcast System
Admins and Managers can create `Broadcast` objects via the Staff Dashboard. If the **SMS** medium is selected, the system resolves all target recipients (Candidates or Staff) and queues bulk SMS tasks.

### B. Exam Lifecycle Notifications
Located in `NotificationService.notify_candidates_about_exam`, SMS alerts are sent for:
1.  **Exam Scheduled**: Sent when an exam is first published and scheduled.
2.  **Exam Reminder**: Sent approximately **1 hour** before the exam start time.
3.  **Exam Started**: Sent immediately when the exam becomes open for candidates.

*Note: These notifications handle grouped delivery (e.g., if multiple candidates share a single guardian's phone number).*

### C. Submission Confirmation
Triggered in `vmlc/views/answer.py`:
- When a candidate successfully submits their exam answers, an SMS confirmation is sent to their registered phone number.

### D. Helpdesk Escalation
Triggered in `comms/tasks.py` (`helpdesk_escalation_task`):
- If a candidate sends a support message during an **ongoing exam** and there is no staff response within **2 minutes**, an "URGENT" SMS alert is sent to all active **Admins and Managers**.

---

## 4. Monitoring and Alerts

### Low Balance Alerts
- **Slack**: `SlackService.send_low_kudi_balance_alert` sends a notification to the configured Slack channel if a bulk SMS task fails due to insufficient funds.
- **Staff Alerts**: The system is designed to alert management if the service is interrupted due to balance issues.

### Placeholder Filtering
The system automatically filters out "placeholder" phone numbers (e.g., `2349123456789`) to avoid wasting SMS credits on test accounts. This is handled via `is_placeholder_phone` in `comms/utils.py`.
