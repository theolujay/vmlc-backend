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
print(','.join(formatted_phones))
"""
exec(code)

code = """
from identity.models import Staff

def format_phone(phone):
    if not phone:
        return ""
    if phone.startswith('0'):
        return '234' + phone[1:]
    if phone.startswith('+234'):
        return phone[1:]
    return phone

phones = Staff.objects.values_list('user__phone', flat=True)
formatted_phones = [format_phone(p) for p in phones if p]
print(','.join(formatted_phones))
"""
exec(code)

code = """
from identity.models import PreRegUser

def format_phone(phone):
    if not phone:
        return ""
    if phone.startswith('0'):
        return '234' + phone[1:]
    if phone.startswith('+234'):
        return phone[1:]
    return phone

phones = PreRegUser.objects.filter(interest_type=PreRegUser.InterestType.CANDIDATE).values_list('phone', flat=True)
formatted_phones = [format_phone(p) for p in phones if p]
print(','.join(formatted_phones))
"""
exec(code)
