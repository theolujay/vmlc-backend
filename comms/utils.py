import logging
from typing import List, Dict
from django.conf import settings
from twilio.rest import Client as TwilioClient
from twilio.base.exceptions import TwilioRestException

logger = logging.getLogger(__name__)

twilio_account_sid = settings.TWILIO_ACCOUNT_SID
twilio_auth_token = settings.TWILIO_AUTH_TOKEN
twilio_from_phone = settings.TWILIO_FROM_PHONE

twilio_client = TwilioClient(twilio_account_sid, twilio_auth_token)


def send_sms(body: str, recipient: str) -> Dict[str, any]:
    """
    Send a single SMS message.

    Returns:
        dict: {"success": bool, "recipient": str, "error": str|None}
    """
    try:
        message = twilio_client.messages.create(
            body=body,
            from_=twilio_from_phone,
            to=recipient,
        )
        logger.info("Sent SMS to %s", recipient[:8] + "***")
        return {"success": True, "recipient": recipient, "error": None}

    except TwilioRestException as e:
        logger.error(
            "Failed to send SMS to %s: [%s] %s",
            recipient[:8] + "***",
            e.code,
            e.msg,
        )
        return {"success": False, "recipient": recipient, "error": str(e)}


def send_bulk_sms(body: str, recipients: List[str]) -> Dict[str, any]:
    """
    Send SMS to multiple recipients.

    Returns:
        dict: {
            "success_count": int,
            "failure_count": int,
            "failed_recipients": List[str],
            "total": int
        }
    """
    logger.info("Sending bulk SMS to %d recipients", len(recipients))

    results = []
    for recipient in recipients:
        result = send_sms(body=body, recipient=recipient)
        results.append(result)

    success_count = sum(1 for r in results if r["success"])
    failure_count = len(results) - success_count
    failed_recipients = [r["recipient"] for r in results if not r["success"]]

    logger.info(
        "Bulk SMS complete: %d succeeded, %d failed out of %d total",
        success_count,
        failure_count,
        len(recipients),
    )

    return {
        "success_count": success_count,
        "failure_count": failure_count,
        "failed_recipients": failed_recipients,
        "total": len(recipients),
    }
