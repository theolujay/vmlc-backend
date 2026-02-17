import logging
import requests

from django.conf import settings

logger = logging.getLogger(__name__)

class SlackService:
    def __init__(self):
        self.webhook_url = getattr(settings, "SLACK_WEBHOOK_URL", None)

    def _send_notification(self, payload):
        if not self.webhook_url:
            logger.warning("SLACK_WEBHOOK_URL is not configured. Skipping Slack notification.")
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
                            "value": backup_log.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC"),
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
