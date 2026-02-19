
def _normalize_phone(phone):
    if not phone:
        return ""
    if phone.startswith('0'):
        return '234' + phone[1:]
    if phone.startswith('+234'):
        return phone[1:]
    return phone

def is_placeholder_phone(phone):
    clean_phone = _normalize_phone(phone)
    return clean_phone == "2349123456789"
