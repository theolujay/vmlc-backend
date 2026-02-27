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


def format_sms_body(subject: str, message: str, max_length: int = 160) -> str:
    """
    Condenses a subject and message into an SMS-friendly format.
    - Strips redundant whitespace and newlines.
    - Combines subject and message with a colon.
    - Truncates intelligently to the max_length.
    """
    # Remove excessive whitespace and newlines
    clean_subject = " ".join(subject.split()) if subject else ""
    clean_message = " ".join(message.split()) if message else ""

    if clean_subject:
        full_body = f"{clean_subject}: {clean_message}"
    else:
        full_body = clean_message

    if len(full_body) <= max_length:
        return full_body

    # If too long, try to truncate the message but keep the subject
    if clean_subject:
        available_for_msg = max_length - len(clean_subject) - 5  # "Subject: ..."
        if available_for_msg > 10:
            return f"{clean_subject}: {clean_message[:available_for_msg]}..."

    # Fallback to simple truncation
    return full_body[: max_length - 3] + "..."
