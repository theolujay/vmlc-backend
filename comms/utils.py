import logging
from time import sleep
from typing import List, Dict, Any

from django.conf import settings
from twilio.rest import Client as TwilioClient
from twilio.base.exceptions import TwilioRestException

from vmlc.utils.exceptions import InvalidMediumError

logger = logging.getLogger(__name__)

# Twilio configuration
twilio_account_sid = settings.TWILIO_ACCOUNT_SID
twilio_auth_token = settings.TWILIO_AUTH_TOKEN
twilio_from_phone = settings.TWILIO_FROM_PHONE

twilio_client = TwilioClient(twilio_account_sid, twilio_auth_token)


def send_phone_msg(body: str, recipient: str, medium: str) -> Dict[str, Any]:
    """
    Send a single message via SMS or WhatsApp.

    Args:
        body: Message content (SMS only, WhatsApp uses templates)
        recipient: Phone number in E.164 format (+2347012345678)
        medium: Either "sms" or "whatsapp"

    Returns:
        dict: {"success": bool, "recipient": str, "error": str|None, "sid": str|None}
    """
    
    if medium not in ["sms", "whatsapp"]:
        raise InvalidMediumError(f"Invalid medium: {medium}. Must be 'sms' or 'whatsapp'")
    
    try:
        if medium == "sms":
            message = twilio_client.messages.create(
                body=body,
                from_=twilio_from_phone,
                to=recipient,
            )
            logger.info(
                "Sent SMS to %s (SID: %s)",
                recipient[:8] + "***",
                message.sid,
            )
            return {
                "success": True,
                "recipient": recipient,
                "error": None,
                "sid": message.sid,
            }
            
        elif medium == "whatsapp":
            # TODO: WhatsApp requires approved templates
            # For now, send as freeform message (sandbox only)
            message = twilio_client.messages.create(
                body=body,  # Only works in Twilio sandbox
                from_=f"whatsapp:{twilio_from_phone}",
                to=f"whatsapp:{recipient}",
            )
            logger.info(
                "Sent WhatsApp to %s (SID: %s)",
                recipient[:8] + "***",
                message.sid,
            )
            return {
                "success": True,
                "recipient": recipient,
                "error": None,
                "sid": message.sid,
            }
            
    except TwilioRestException as e:
        logger.error(
            "Failed to send %s to %s: [%s] %s",
            medium.upper(),
            recipient[:8] + "***",
            e.code,
            e.msg,
        )
        return {
            "success": False,
            "recipient": recipient,
            "error": f"[{e.code}] {e.msg}",
            "sid": None,
        }


def send_bulk_phone_msg(
    body: str,
    recipients: List[str],
    medium: str,
    delay: float = 0.1,  # 100ms default (10 msgs/sec)
) -> Dict[str, Any]:
    """
    Send messages to multiple recipients via SMS or WhatsApp.

    Args:
        body: Message content
        recipients: List of phone numbers in E.164 format
        medium: Either "sms" or "whatsapp"
        delay: Seconds to wait between sends (default: 0.1)

    Returns:
        dict: {
            "success_count": int,
            "failure_count": int,
            "failed_recipients": List[str],
            "total": int
        }
    """
    if not recipients:
        logger.warning("No recipients provided for bulk %s", medium)
        return {
            "success_count": 0,
            "failure_count": 0,
            "failed_recipients": [],
            "total": 0,
        }
    
    logger.info("Sending bulk %s to %d recipients", medium.upper(), len(recipients))

    results = []
    for i, recipient in enumerate(recipients, 1):
        result = send_phone_msg(body=body, recipient=recipient, medium=medium)
        results.append(result)
        
        # Rate limiting: don't delay after the last message
        if i < len(recipients) and delay > 0:
            sleep(delay)

    success_count = sum(1 for r in results if r["success"])
    failure_count = len(results) - success_count
    failed_recipients = [r["recipient"] for r in results if not r["success"]]

    logger.info(
        "Bulk %s complete: %d succeeded, %d failed out of %d total",
        medium.upper(),
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