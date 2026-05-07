import re


def _normalize_phone(phone):
    if not phone:
        return ""
    if phone.startswith("0"):
        return "234" + phone[1:]
    if phone.startswith("+234"):
        return phone[1:]
    return phone


def is_placeholder_phone(phone):
    clean_phone = _normalize_phone(phone)
    return clean_phone == "2349123456789"


def format_sms_body(subject: str, message: str) -> str:
    """
    Condenses a subject and message into an SMS-friendly format.
    Strips redundant whitespace and newlines, combines subject and message.
    """
    clean_subject = " ".join(subject.split()) if subject else ""
    clean_message = " ".join(message.split()) if message else ""

    if clean_subject:
        return f"{clean_subject}: \n{clean_message}"

    return clean_message
