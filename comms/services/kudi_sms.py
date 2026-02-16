import json
import logging
import requests
from enum import Enum
from typing import Dict, List, Optional, Any

from django.conf import settings

logger = logging.getLogger(__name__)

SENDER_ID = getattr(settings, "KUDI_SENDER_ID", "VMLC")
API_KEY = getattr(settings, "KUDI_API_KEY", "")
GATEWAY = getattr(settings, "KUDI_GATEWAY", "direct-delivery")
COST_PER_MSG = 5.6  # Default cost in Naira


class KudiURL(Enum):
    BULK_SMS = "https://my.kudisms.net/api/sms"
    SMS_OTP = "https://my.kudisms.net/api/otp"
    BALANCE = "https://my.kudisms.net/api/balance"
    PERSONALISED_SMS = "https://my.kudisms.net/api/personalisedsms"


def parse_balance(balance_str: str) -> float:
    """Parse balance string like '15,585.41' to float."""
    try:
        return float(balance_str.replace(",", ""))
    except (ValueError, AttributeError):
        return 0.0


def estimate_cost(message: str, recipient_count: int) -> float:
    """
    Estimate the cost of sending an SMS.
    160 characters = 1 page.
    Concatenated SMS uses 153 chars/page.
    """
    msg_len = len(message)
    if msg_len <= 160:
        pages = 1
    else:
        # For multi-page messages, Kudi/GSM uses ~153 chars per segment
        import math
        pages = math.ceil(msg_len / 153)
    
    return pages * recipient_count * COST_PER_MSG


def _make_request(url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Internal helper to handle requests to Kudi SMS API.
    """
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(
            url,
            headers=headers,
            data=json.dumps(payload),
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        
        # Log balance if present in response
        if "balance" in data:
            current_balance = parse_balance(data["balance"])
            logger.info(f"Kudi SMS Balance: {current_balance} Naira")
            
            # Cache the balance for 1 hour
            from django.core.cache import cache
            cache.set("kudi_sms_balance", current_balance, 3600)
            
        return data
    except requests.exceptions.RequestException as e:
        logger.error(f"Kudi SMS API error: {e}")
        if hasattr(e.response, "text"):
            logger.error(f"Response: {e.response.text}")
        return {"status": "error", "message": str(e)}
    except json.JSONDecodeError:
        logger.error(f"Kudi SMS API returned invalid JSON: {response.text}")
        return {"status": "error", "message": "Invalid JSON response"}


def send_bulk_sms(message: str, recipients: str) -> Dict[str, Any]:
    """
    Send bulk SMS to one or more recipients (comma separated).
    """
    payload = {
        "token": API_KEY,
        "senderID": SENDER_ID,
        "message": message,
        "recipients": recipients,
        "gateway": GATEWAY,
    }
    return _make_request(KudiURL.BULK_SMS.value, payload)


def send_personalised_sms(message: str, recipients: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Send personalised SMS where recipients list contains dicts with replacement values.
    Example:
        recipients=[
            {"phone_number": "234703xxxxx", "name": "Nath"},
            {"phone_number": "234802xxxxx", "name": "John"}
        ]
    """
    payload = {
        "token": API_KEY,
        "senderID": SENDER_ID,
        "message": message,
        "recipients": recipients,
    }
    return _make_request(KudiURL.PERSONALISED_SMS.value, payload)


def get_balance() -> Dict[str, Any]:
    """
    Check the current Kudi SMS wallet balance.
    """
    payload = {"token": API_KEY}
    return _make_request(KudiURL.BALANCE.value, payload)

# This requires a Corporate Sender ID, so it's not to be used until we have that
def send_otp(mobile: str, message: Optional[str] = None) -> Dict[str, Any]:
    """
    Send an OTP to a mobile number.
    If message is None, Kudi will generate and send a default OTP message.
    """
    payload = {
        "token": API_KEY,
        "senderID": SENDER_ID,
        "mobile": mobile,
    }
    if message:
        payload["message"] = message

    return _make_request(KudiURL.SMS_OTP.value, payload)
