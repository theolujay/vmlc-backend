code = r"""
from identity.models import Candidate
from collections import defaultdict

def format_phone(phone):
    if not phone:
        return ""
    if phone.startswith('0'):
        return '234' + phone[1:]
    if phone.startswith('+234'):
        return phone[1:]
    return phone

def is_placeholder(phone):
    return phone == "2349123456789"

# Group candidates by phone number
phone_to_candidates = defaultdict(list)

all_candidates = Candidate.objects.all()

for candidate in all_candidates:
    clean_phone = format_phone(candidate.user.phone)
    if not is_placeholder(clean_phone):
        phone_to_candidates[clean_phone].append({
            'name': candidate.user.get_full_name(),
            'email': candidate.user.email,
            'school': candidate.school_name,
            'state': candidate.user.state,
            'date_joined': candidate.user.date_joined.strftime("%A, %B %d, %Y at %I:%M %p") if candidate.user.date_joined else "N/A",
        })

# Filter only shared numbers (more than 1 candidate)
shared_numbers = {phone: candidates for phone, candidates in phone_to_candidates.items()
                  if len(candidates) > 1}

# Statistics
total_shared_numbers = len(shared_numbers)
total_candidates_affected = sum(len(candidates) for candidates in shared_numbers.values())

print("=" * 80)
print("SHARED PHONE NUMBER ANALYSIS")
print("=" * 80)
print(f"\nTotal unique phone numbers with duplicates: {total_shared_numbers}")
print(f"Total candidates affected: {total_candidates_affected}")
print(f"Percentage of SMS-ready candidates sharing numbers: {(total_candidates_affected/343)*100:.1f}%")
print("\n" + "=" * 80)

# Sort by number of users per phone (most duplicates first)
sorted_shared = sorted(shared_numbers.items(), key=lambda x: len(x[1]), reverse=True)

print("\nDETAILED BREAKDOWN (sorted by most shared):\n")

for idx, (phone, candidates) in enumerate(sorted_shared, 1):
    print(f"{idx}. Phone: {phone} ({len(candidates)} candidates)")
    print("-" * 80)
    for i, c in enumerate(candidates, 1):
        print(f"   {i}. {c['name']}")
        print(f"      Email: {c['email']}")
        print(f"      School: {c['school']}")
        print(f"      State: {c['state']}")
        print(f"      Joined: {c['date_joined']}")
        print()
    print()

# Summary by duplicate count
print("=" * 80)
print("SUMMARY BY DUPLICATE COUNT")
print("=" * 80)
from collections import Counter
duplicate_counts = Counter(len(candidates) for candidates in shared_numbers.values())

for count in sorted(duplicate_counts.keys(), reverse=True):
    print(f"{duplicate_counts[count]} phone number(s) shared by {count} candidates each")
"""
exec(code)
















code = r"""
from identity.models import Candidate

def format_phone(phone):
    if not phone:
        return ""
    if phone.startswith('0'):
        return '234' + phone[1:]
    if phone.startswith('+234'):
        return phone[1:]
    return phone

def is_placeholder(phone):
    return phone == "2349123456789"

placeholder_users = []
sms_ready_phones = []

all_candidates = Candidate.objects.all()

for candidate in all_candidates:
    clean_phone = format_phone(candidate.user.phone)
    if is_placeholder(clean_phone):
        placeholder_users.append(
            [
                candidate.user.email,
                candidate.user.get_full_name(),
                candidate.school_name,
                candidate.user.state,
                candidate.user.date_joined,
            ]
        )
    else:
        sms_ready_phones.append(clean_phone)


unique_sms_phones = list(set(sms_ready_phones))
print(f"Total candidates: {all_candidates.count()}")
print(f"Total SMS-ready: {len(sms_ready_phones)}")
print(f"Unique numbers: {len(unique_sms_phones)}")
print(f"Duplicates: {len(sms_ready_phones) - len(unique_sms_phones)}")

print(f"\nUnique phone list for SMS service:")
print(",".join(unique_sms_phones))
print("\n============================\n")
for idx, candidate in enumerate(placeholder_users):
    print(f"{idx + 1}. {candidate}")
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
