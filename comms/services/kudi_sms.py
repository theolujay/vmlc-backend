import json
import logging
from enum import Enum
from typing import Any, Dict, List, Optional

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class KudiURL(Enum):
    BULK_SMS = "https://my.kudisms.net/api/sms"
    SMS_OTP = "https://my.kudisms.net/api/otp"
    BALANCE = "https://my.kudisms.net/api/balance"
    PERSONALISED_SMS = "https://my.kudisms.net/api/personalisedsms"


class KudiSmsService:
    def __init__(self):
        self.sender_id = getattr(settings, "KUDI_SENDER_ID")
        self.api_key = getattr(settings, "KUDI_API_KEY")
        self.gateway = getattr(settings, "KUDI_GATEWAY")
        self.cost_per_msg = 5.6  # Default cost in Naira

    def parse_balance(self, balance_str: str) -> float:
        """Parse balance string like '15,585.41' to float."""
        try:
            return float(balance_str.replace(",", ""))
        except (ValueError, AttributeError):
            return 0.0

    def estimate_cost(self, message: str, recipient_count: int) -> float:
        """
        Estimate the cost of sending an SMS.
        160 characters = 1 page.
        Concatenated SMS uses 153 chars/page.
        """
        msg_len = len(message)
        if msg_len <= 160:
            pages = 1
        else:
            import math

            pages = math.ceil(msg_len / 153)

        return pages * recipient_count * self.cost_per_msg

    def _make_request(
        self, url: str, payload: Dict[str, Any], method: str = "POST"
    ) -> Dict[str, Any]:
        """Internal helper to handle requests to Kudi SMS API."""
        headers = {}
        try:
            if method.upper() == "POST":
                headers["Content-Type"] = "application/json"
                response = requests.post(
                    url,
                    headers=headers,
                    data=json.dumps(payload),
                    timeout=30,
                )
            else:  # GET
                response = requests.get(
                    url,
                    params=payload,
                    timeout=30,
                )

            response.raise_for_status()
            data = response.json()

            if "api/balance" in url:
                if data.get("status") == "success" and "msg" in data:
                    return {"balance": data["msg"]}
                else:
                    return {"balance": "0", "error": data.get("msg", "Unknown error")}

            if "balance" in data:
                current_balance = self.parse_balance(data["balance"])
                logger.info(f"Kudi SMS Balance: {current_balance} Naira")
                cache.set("kudi_sms_balance", current_balance, 3600)

            return data
        except requests.exceptions.RequestException as e:
            logger.error(f"Kudi SMS API error: {e}")
            if hasattr(e.response, "text"):
                logger.error(f"Response: {e.response.text}")
            return {"status": "error", "message": str(e)}
        except json.JSONDecodeError as e:
            logger.error(f"Kudi SMS API returned invalid JSON: {e.response.text}")
            return {"status": "error", "message": "Invalid JSON response"}

    def send_bulk_sms(self, message: str, recipients: str) -> Dict[str, Any]:
        """Send bulk SMS to one or more recipients (comma separated)."""
        payload = {
            "token": self.api_key,
            "senderID": self.sender_id,
            "message": message,
            "recipients": recipients,
            "gateway": self.gateway,
        }
        return self._make_request(KudiURL.BULK_SMS.value, payload)

    def send_personalised_sms(
        self, message: str, recipients: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """Send personalised SMS."""
        payload = {
            "token": self.api_key,
            "senderID": self.sender_id,
            "message": message,
            "recipients": recipients,
        }
        return self._make_request(KudiURL.PERSONALISED_SMS.value, payload)

    def get_balance(self) -> Dict[str, Any]:
        """Check the current Kudi SMS wallet balance."""
        payload = {"token": self.api_key}
        return self._make_request(KudiURL.BALANCE.value, payload, method="GET")

    def send_otp(self, mobile: str, message: Optional[str] = None) -> Dict[str, Any]:
        """Send an OTP to a mobile number."""
        payload = {
            "token": self.api_key,
            "senderID": self.sender_id,
            "mobile": mobile,
        }
        if message:
            payload["message"] = message

        return self._make_request(KudiURL.SMS_OTP.value, payload)
