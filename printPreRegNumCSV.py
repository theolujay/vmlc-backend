code = """
from identity.models import Candidate

def format_phone(phone):
    if not phone:
        return ""
    if phone.startswith('0'):
        return '234' + phone[1:]
    if phone.startswith('+234'):
        return phone[1:]
    return phone

phones = Candidate.objects.values_list('user__phone', flat=True)
formatted_phones = [format_phone(p) for p in phones if p]
print(','.join(formatted_phones))gem
"""
exec(code)