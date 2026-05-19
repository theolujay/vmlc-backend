import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class SlackService:
    def __init__(self):
        self.webhook_url = getattr(settings, "SLACK_WEBHOOK_URL", None)

    def _send_notification(self, payload):
        if not self.webhook_url:
            logger.warning(
                "SLACK_WEBHOOK_URL is not configured. Skipping Slack notification."
            )
            return False
        try:
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            logger.info("Slack notification sent successfully.")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send Slack notification: {e}")
            return False

    def send_low_kudi_balance_alert(
        self, current_balance: float, estimated_cost: float, recipient_count: int
    ):
        """Sends a notification about low Kudi SMS balance to a Slack channel."""
        payload = {
            "text": ":warning: Low Kudi SMS Balance Alert",
            "attachments": [
                {
                    "color": "danger",
                    "fields": [
                        {
                            "title": "Environment",
                            "value": settings.APP_ENVIRONMENT.title(),
                            "short": True,
                        },
                        {
                            "title": "Action",
                            "value": "Top-up Kudi SMS account",
                            "short": True,
                        },
                        {
                            "title": "Current Balance",
                            "value": f"₦{current_balance:,.2f}",
                            "short": True,
                        },
                        {
                            "title": "Required for Send",
                            "value": f"₦{estimated_cost:,.2f} for {recipient_count} recipients",
                            "short": True,
                        },
                    ],
                }
            ],
        }
        return self._send_notification(payload)

    def send_backup_status(self, backup_log):
        """Sends a notification about the backup status to a Slack channel."""
        status = backup_log.status
        if status in [backup_log.Status.SUCCESS, backup_log.Status.SUCCESS_AFTER_RETRY]:
            color = "good"
        else:
            color = "danger"

        payload = {
            "text": f"DB Backup for {backup_log.get_environment_display()}: {backup_log.get_status_display()}",
            "attachments": [
                {
                    "color": color,
                    "fields": [
                        {
                            "title": "Environment",
                            "value": backup_log.get_environment_display(),
                            "short": True,
                        },
                        {
                            "title": "Status",
                            "value": backup_log.get_status_display(),
                            "short": True,
                        },
                        {
                            "title": "Backup File",
                            "value": backup_log.backup_filename,
                            "short": False,
                        },
                        {
                            "title": "Timestamp",
                            "value": backup_log.timestamp.strftime(
                                "%Y-%m-%d %H:%M:%S UTC"
                            ),
                            "short": False,
                        },
                    ],
                }
            ],
        }

        if backup_log.error_message:
            payload["attachments"][0]["fields"].append(
                {
                    "title": "Error Message",
                    "value": backup_log.error_message,
                    "short": False,
                }
            )

        return self._send_notification(payload)

    def send_support_escalation_alert(self, thread, latest_message):
        """Sends a notification about a pending support message to a Slack channel."""
        payload = {
            "text": ":rotating_light: Support Escalation Alert",
            "attachments": [
                {
                    "color": "danger",
                    "fields": [
                        {
                            "title": "Candidate",
                            "value": thread.candidate.user.get_full_name(),
                            "short": True,
                        },
                        {
                            "title": "Email",
                            "value": thread.candidate.user.email,
                            "short": True,
                        },
                        {
                            "title": "Thread ID",
                            "value": f"{thread.id}",
                            "short": True,
                        },
                        {
                            "title": "Waiting For",
                            "value": "Over 2 minutes",
                            "short": True,
                        },
                        {
                            "title": "Latest Message",
                            "value": latest_message.text,
                            "short": False,
                        },
                    ],
                }
            ],
        }
        return self._send_notification(payload)

    def send_exam_status_notification(self, exam, event_type: str):
        """Sends a notification about an exam status change to a Slack channel."""

        color_map = {
            "ongoing": "good",
            "concluded": "warning",
            "cancelled": "danger",
        }

        payload = {
            "text": f":bell: Exam Status Update: {exam.get_title()}",
            "attachments": [
                {
                    "color": color_map.get(event_type, "#439FE0"),
                    "fields": [
                        {
                            "title": "Exam",
                            "value": exam.get_title(),
                            "short": True,
                        },
                        {
                            "title": "New Status",
                            "value": event_type.capitalize(),
                            "short": True,
                        },
                        {
                            "title": "Environment",
                            "value": settings.APP_ENVIRONMENT.title(),
                            "short": True,
                        },
                    ],
                }
            ],
        }
        return self._send_notification(payload)

    def send_ranking_published_notification(self, ranking):
        """Sends a notification about a published ranking snapshot to a Slack channel."""
        exam = ranking.exam
        payload = {
            "text": f":trophy: Results Published: {exam.get_title()}",
            "attachments": [
                {
                    "color": "#3E4095",
                    "fields": [
                        {
                            "title": "Exam",
                            "value": exam.get_title(),
                            "short": True,
                        },
                        {
                            "title": "Stage",
                            "value": ranking.get_stage_display(),
                            "short": True,
                        },
                        {
                            "title": "Round",
                            "value": str(ranking.round) if ranking.round else "N/A",
                            "short": True,
                        },
                        {
                            "title": "Candidates",
                            "value": str(ranking.entries.count()),
                            "short": True,
                        },
                        {
                            "title": "Environment",
                            "value": settings.APP_ENVIRONMENT.title(),
                            "short": True,
                        },
                    ],
                }
            ],
        }
        return self._send_notification(payload)
