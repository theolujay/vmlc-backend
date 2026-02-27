code = r"""
from identity.models import Candidate
from collections import defaultdict, Counter

def _normalize_phone(phone):
    if not phone:
        return ""
    if phone.startswith('0'):
        return '234' + phone[1:]
    if phone.startswith('+234'):
        return phone[1:]
    return phone

def is_placeholder(phone):
    return phone == "2349123456789"

# Collect all data
phone_to_candidates = defaultdict(list)
placeholder_users = []
sms_ready_phones = []

all_candidates = Candidate.objects.all()

for candidate in all_candidates:
    clean_phone = _normalize_phone(candidate.user.phone)
    if is_placeholder(clean_phone):
        placeholder_users.append({
            'name': candidate.user.get_full_name(),
            'email': candidate.user.email,
            'school': candidate.school_name,
            'state': candidate.user.state,
            'date_joined': candidate.user.date_joined.strftime("%A, %B %d, %Y at %I:%M %p") if candidate.user.date_joined else "N/A",
            'last_login': candidate.user.last_login,
        })
    else:
        sms_ready_phones.append(clean_phone)
        phone_to_candidates[clean_phone].append({
            'name': candidate.user.get_full_name(),
            'email': candidate.user.email,
            'school': candidate.school_name,
            'state': candidate.user.state,
            'date_joined': candidate.user.date_joined,
            'last_login': candidate.user.last_login,
        })

# Filter shared numbers
shared_numbers = {phone: candidates for phone, candidates in phone_to_candidates.items()
                  if len(candidates) > 1}

# Statistics
total_candidates = all_candidates.count()
total_sms_ready = len(sms_ready_phones)
unique_sms_phones = list(set(sms_ready_phones))
total_unique_numbers = len(unique_sms_phones)
total_duplicates = total_sms_ready - total_unique_numbers
total_shared_numbers = len(shared_numbers)
total_candidates_affected = sum(len(candidates) for candidates in shared_numbers.values())
total_placeholder = len(placeholder_users)

# Analyze patterns
bulk_registrations = []  # School/guardian registering multiple students
duplicate_accounts = []  # Same student, multiple accounts (likely confusion)
family_sharing = []      # Different students, same phone (likely siblings/family)

for phone, candidates in shared_numbers.items():
    # Group by name
    name_groups = defaultdict(list)
    for c in candidates:
        name_groups[c['name']].append(c)

    # Check if it's the same person with multiple accounts
    for name, accounts in name_groups.items():
        if len(accounts) >= 2:
            # Same name, multiple accounts - likely confusion during registration
            duplicate_accounts.append({
                'phone': phone,
                'name': name,
                'count': len(accounts),
                'school': accounts[0]['school'],
                'emails': [a['email'] for a in accounts],
                'registration_dates': [a['date_joined'] for a in accounts],
                'accounts': accounts
            })

    # Check for bulk school registrations
    # All from same school, registered on same day within short time window
    if len(candidates) >= 5:
        schools = [c['school'] for c in candidates]
        dates = [c['date_joined'].date() for c in candidates]

        # If all from same school and registered on same day
        if len(set(schools)) == 1 and len(set(dates)) == 1:
            time_window = max([c['date_joined'] for c in candidates]) - min([c['date_joined'] for c in candidates])
            if time_window.total_seconds() <= 7200:  # Within 2 hours
                bulk_registrations.append({
                    'phone': phone,
                    'school': schools[0],
                    'count': len(candidates),
                    'date': dates[0],
                    'time_window_minutes': int(time_window.total_seconds() / 60),
                    'candidates': candidates
                })

    # Check for family sharing (different names, same phone)
    unique_names = set(c['name'] for c in candidates)
    if len(unique_names) == len(candidates) and len(candidates) >= 2:
        # All different people - likely family members
        family_sharing.append({
            'phone': phone,
            'count': len(candidates),
            'candidates': candidates
        })

# Sort analyses
bulk_registrations.sort(key=lambda x: x['count'], reverse=True)
duplicate_accounts.sort(key=lambda x: x['count'], reverse=True)
family_sharing.sort(key=lambda x: x['count'], reverse=True)
sorted_shared = sorted(shared_numbers.items(), key=lambda x: len(x[1]), reverse=True)

# ============================================================================
# PRINT COMPREHENSIVE REPORT
# ============================================================================

print("=" * 100)
print(" " * 35 + "COMPREHENSIVE CANDIDATE ANALYSIS")
print("=" * 100)

# OVERVIEW STATISTICS
print("\n" + "=" * 100)
print("OVERVIEW STATISTICS")
print("=" * 100)
print(f"Total Candidates:                    {total_candidates}")
print(f"SMS-Ready Candidates:                {total_sms_ready} ({(total_sms_ready/total_candidates)*100:.1f}%)")
print(f"Unique Phone Numbers:                {total_unique_numbers}")
print(f"Duplicate Phone Numbers:             {total_duplicates} ({(total_duplicates/total_sms_ready)*100:.1f}%)")
print(f"Placeholder Phone Numbers:           {total_placeholder} ({(total_placeholder/total_candidates)*100:.1f}%)")
print(f"\nPhone Numbers Shared:                {total_shared_numbers}")
print(f"Candidates Affected by Sharing:      {total_candidates_affected} ({(total_candidates_affected/total_sms_ready)*100:.1f}%)")

# PATTERN ANALYSIS
print("\n" + "=" * 100)
print("PATTERN ANALYSIS")
print("=" * 100)
print(f"Bulk School Registrations:           {len(bulk_registrations)} instances (likely guardian/teacher registering)")
print(f"Duplicate Accounts (Same Person):    {len(duplicate_accounts)} instances (likely registration confusion)")
print(f"Family Sharing:                      {len(family_sharing)} instances (likely siblings/family members)")

# DUPLICATE ACCOUNTS - Same student, multiple registrations
if duplicate_accounts:
    print("\n" + "=" * 100)
    print("DUPLICATE ACCOUNTS - SAME STUDENT, MULTIPLE REGISTRATIONS")
    print("=" * 100)
    print("These are likely students who got confused during registration and created multiple accounts.\n")

    for idx, dup in enumerate(duplicate_accounts, 1):
        print(f"{idx}. {dup['name']} - {dup['count']} accounts")
        print(f"   Phone: {dup['phone']}")
        print(f"   School: {dup['school']}")
        print(f"   Emails: {', '.join(dup['emails'])}")
        print(f"   Registration & Login Activity:")

        # Analyze login patterns
        accounts_with_login = []
        accounts_never_logged_in = []

        for account in dup['accounts']:
            reg_time = account['date_joined'].strftime('%A, %B %d, %Y at %I:%M %p')
            last_login = account['last_login']

            if last_login:
                login_time = last_login.strftime('%A, %B %d, %Y at %I:%M %p')
                print(f"      - {account['email']}")
                print(f"        Registered: {reg_time}")
                print(f"        Last Login: {login_time} ✓")
                accounts_with_login.append(account)
            else:
                print(f"      - {account['email']}")
                print(f"        Registered: {reg_time}")
                print(f"        Last Login: Never logged in ✗")
                accounts_never_logged_in.append(account)

        # Analysis summary for this duplicate
        print(f"\n   Analysis:")
        if len(accounts_never_logged_in) == len(dup['accounts']):
            print(f"      - All {len(dup['accounts'])} accounts have NEVER logged in")
            print(f"      - Likely: Student didn't receive registration emails (check spam/incorrect email)")
            print(f"      - Action: Send password reset to all emails or contact via phone")
        elif len(accounts_with_login) == 1:
            print(f"      - Only 1 account has been used (logged in)")
            print(f"      - Active account: {accounts_with_login[0]['email']}")
            print(f"      - Action: Keep active account, delete/merge the {len(accounts_never_logged_in)} unused account(s)")
        elif len(accounts_with_login) > 1:
            print(f"      - Multiple accounts ({len(accounts_with_login)}) have been logged into")
            print(f"      - Student is actively using multiple accounts")
            print(f"      - Action: Contact student to consolidate accounts")
        else:
            print(f"      - Mixed login activity detected")
            print(f"      - Action: Manual review recommended")

        print()

# BULK SCHOOL REGISTRATIONS
if bulk_registrations:
    print("\n" + "=" * 100)
    print("BULK SCHOOL REGISTRATIONS")
    print("=" * 100)
    print("These are likely guardians, teachers, or school administrators registering multiple students.\n")

    for idx, bulk in enumerate(bulk_registrations, 1):
        print(f"{idx}. {bulk['school']} - {bulk['count']} students")
        print(f"   Phone: {bulk['phone']}")
        print(f"   Registration Date: {bulk['date'].strftime('%A, %B %d, %Y')}")
        print(f"   Time Window: {bulk['time_window_minutes']} minutes")
        print(f"   Students:")
        for c in bulk['candidates']:
            print(f"      - {c['name']} ({c['email']}) at {c['date_joined'].strftime('%I:%M %p')}")
        print()

# FAMILY SHARING
if family_sharing:
    print("\n" + "=" * 100)
    print("FAMILY SHARING")
    print("=" * 100)
    print("These are likely siblings or family members sharing a parent's/guardian's phone number.\n")

    for idx, fam in enumerate(family_sharing, 1):
        if fam['count'] >= 3:  # Only show cases with 3+ family members
            print(f"{idx}. Phone: {fam['phone']} - {fam['count']} students")
            schools = list(set(c['school'] for c in fam['candidates']))
            print(f"   School(s): {', '.join(schools)}")
            print(f"   Students:")
            for c in fam['candidates']:
                print(f"      - {c['name']} ({c['email']})")
            print()

# DETAILED BREAKDOWN
print("\n" + "=" * 100)
print("DETAILED BREAKDOWN - ALL SHARED PHONE NUMBERS")
print("=" * 100)
print()

for idx, (phone, candidates) in enumerate(sorted_shared, 1):
    print(f"{idx}. Phone: {phone} ({len(candidates)} candidates)")
    print("-" * 100)
    for i, c in enumerate(candidates, 1):
        print(f"   {i}. {c['name']}")
        print(f"      Email: {c['email']}")
        print(f"      School: {c['school']}")
        print(f"      State: {c['state']}")
        print(f"      Joined: {c['date_joined'].strftime('%A, %B %d, %Y at %I:%M %p')}")
        print()
    print()

# SUMMARY BY DUPLICATE COUNT
print("=" * 100)
print("SUMMARY BY DUPLICATE COUNT")
print("=" * 100)
duplicate_counts = Counter(len(candidates) for candidates in shared_numbers.values())
for count in sorted(duplicate_counts.keys(), reverse=True):
    print(f"{duplicate_counts[count]} phone number(s) shared by {count} candidates each")

# PLACEHOLDER USERS
if placeholder_users:
    print("\n" + "=" * 100)
    print("PLACEHOLDER PHONE NUMBERS - NEED EMAIL CONTACT")
    print("=" * 100)
    print(f"Total: {total_placeholder} candidates\n")

    for idx, user in enumerate(placeholder_users, 1):
        print(f"{idx}. {user['name']}")
        print(f"   Email: {user['email']}")
        print(f"   School: {user['school']}")
        print(f"   State: {user['state']}")
        print(f"   Joined: {user['date_joined']}")
        print()

# RECOMMENDATIONS
print("\n" + "=" * 100)
print("RECOMMENDATIONS FOR HANDLING DUPLICATES")
print("=" * 100)

print("\n1. FOR SMS CAMPAIGN:")
print("   - Use the unique phone list (265 numbers) to avoid duplicate messages")
print("   - This will save costs and prevent annoying recipients")
print("   - All students will still be reached (shared phones are legitimate)")

print("\n2. FOR DUPLICATE ACCOUNTS (Same student, multiple registrations):")
print(f"   - Identified {len(duplicate_accounts)} students with multiple accounts")
print("   - Check the login activity analysis above to determine:")
print("     * Never logged in = Email delivery issue (check spam filters, typos)")
print("     * One active account = Keep the active one, delete unused accounts")
print("     * Multiple active accounts = Student confused, needs consolidation")
print("   - Action: Merge accounts or mark duplicates for manual review")
print("   - UX Improvement: Consider adding 'Already have an account?' prompt during registration")
print("   - Email Improvement: Ensure registration confirmation emails are being delivered")

print("\n3. FOR BULK SCHOOL REGISTRATIONS:")
print(f"   - Identified {len(bulk_registrations)} bulk registration instances")
print("   - Action: These are fine - guardians/teachers helping students register")
print("   - Consider: Send one SMS to the guardian explaining they'll receive updates for multiple students")

print("\n4. FOR FAMILY SHARING:")
print(f"   - Identified {len(family_sharing)} family sharing instances")
print("   - Action: These are fine - legitimate siblings/family members")
print("   - The parent/guardian will receive updates for all their children")

print("\n5. FOR PLACEHOLDER USERS:")
print(f"   - Contact these {total_placeholder} users via email")
print("   - Request valid phone numbers for SMS communication")
print("   - Follow up to ensure they can participate fully")

print("\n6. REGISTRATION PROCESS IMPROVEMENTS:")
print("   - If many 'never logged in' duplicates: Improve email deliverability")
print("   - Add 'Already registered? Login here' link on registration page")
print("   - Send immediate confirmation SMS upon successful registration")
print("   - Consider email verification before account activation")

# EXPORT UNIQUE PHONE LIST
print("\n" + "=" * 100)
print("UNIQUE PHONE LIST FOR SMS SERVICE")
print("=" * 100)
print(f"\nTotal Unique Numbers: {total_unique_numbers}\n")
print(",".join(unique_sms_phones))

print("\n" + "=" * 100)
print("END OF REPORT")
print("=" * 100)
"""
exec(code)
