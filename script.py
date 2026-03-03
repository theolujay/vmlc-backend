code = r"""
from django.contrib.auth import get_user_model
from competition.models import Enrollment
from identity.models import Candidate
from django.db import transaction

with transaction.atomic():
    User = get_user_model()

    # Get the IDs of all users who are linked to a candidate and have an unverified email.
    user_ids_to_deactivate = Candidate.objects.filter(
        user__is_email_verified=False
    ).values_list("user_id", flat=True)

    # Deactivate all those users in a single, efficient database query.
    update_count = User.objects.filter(id__in=user_ids_to_deactivate).update(
        is_active=False
    )
    print(f"Deactivated {update_count} users.")

    # Also delete their enrollments in the same transaction
    enrollment_delete_count, _ = Enrollment.objects.filter(
        candidate__user_id__in=user_ids_to_deactivate
    ).delete()
    print(f"Deleted {enrollment_delete_count} enrollments.")

    # --- VERIFICATION STEP ---
    # To prove the change happened in the database, let's check one user.
    if update_count > 0:
        # Clone the queryset before it's fully consumed to use it again
        user_ids_list = list(user_ids_to_deactivate[:1])
        if user_ids_list:
            one_user_id = user_ids_list[0]
            # Re-fetch the user directly from the database
            user_for_verification = User.objects.get(id=one_user_id)
            print(
                f"Verification check: User ID {user_for_verification.id} is_active is now: {user_for_verification.is_active}"
            )
"""
exec(code)

code2 = r"""
from django.contrib.auth import get_user_model
from competition.models import Enrollment
from identity.models import Candidate
from django.db import transaction

User = get_user_model()


active_user_ids = Candidate.objects.filter(
    user__last_login__isnull=False
).values_list("user_id", flat=True)

inactive_user_ids = Candidate.objects.filter(
    user__last_login__isnull=True
).values_list("user_id", flat=True)

# update_count = User.objects.filter(id__in=user_ids_to_deactivate).update(
#     is_active=False
# )
print(f"{len(active_user_ids)} candidates logged in.")
print(f"{len(inactive_user_ids)} candidates did not log in")

all_enrollment_ids = Enrollment.objects.all().values_list("candidate_id")
print(f"{len(all_enrollment_ids)} enrollments found")

enrolled_candidate_ids = Enrollment.objects.values_list("candidate__user_id", flat=True)

active_candidates_without_enrollment = Candidate.objects.filter(
    user__is_active=True,
).exclude(
    user_id__in=enrolled_candidate_ids
)

inactive_candidates_without_enrollment = Candidate.objects.filter(
    user__is_active=False,
).exclude(
    user_id__in=enrolled_candidate_ids
)

verified_candidates_without_enrollment = Candidate.objects.filter(
    user__is_email_verified=True,
).exclude(
    user_id__in=enrolled_candidate_ids
)

unverified_candidates_without_enrollment = Candidate.objects.filter(
    user__is_email_verified=False,
).exclude(
    user_id__in=enrolled_candidate_ids
)

if len(active_candidates_without_enrollment) == 0:
    print("No active candidates without enrollments found")
else:
    for candidate in active_candidates_without_enrollment:
        print(f"{candidate.user.id} - {candidate.user.get_full_name()} - {candidate.user.email}")

if len(inactive_candidates_without_enrollment) == 0:
    print("No inactive candidates without enrollments found")
else:
    for candidate in inactive_candidates_without_enrollment:
        print(f"{candidate.user.id} - {candidate.user.get_full_name()} - {candidate.user.email}")

if len(verified_candidates_without_enrollment) == 0:
    print("No verified candidates without enrollments found")
else:
    for candidate in verified_candidates_without_enrollment:
        print(f"{candidate.user.id} - {candidate.user.get_full_name()} - {candidate.user.email}")

if len(unverified_candidates_without_enrollment) == 0:
    print("No verified candidates without enrollments found")
else:
    for candidate in unverified_candidates_without_enrollment:
        print(f"{candidate.user.id} - {candidate.user.get_full_name()} - {candidate.user.email}")
"""
exec(code2)

code3 = r"""
from django.contrib.auth import get_user_model
from competition.models import Enrollment
from identity.models import Candidate

User = get_user_model()

# --- Stats ---
print(f"{Candidate.objects.filter(user__last_login__isnull=False).count()} candidates have logged in.")
print(f"{Candidate.objects.filter(user__last_login__isnull=True).count()} candidates have never logged in.")
print(f"{Enrollment.objects.count()} enrollments found.")

# --- Helpers ---
enrolled_candidate_ids = Enrollment.objects.values_list("candidate__user_id", flat=True)

unenrolled = Candidate.objects.exclude(user_id__in=enrolled_candidate_ids).select_related("user")

def print_candidates(label, queryset):
    candidates = list(queryset)
    if not candidates:
        print(f"No {label} candidates without enrollments found.")
        return
    print(f"\n--- {label} candidates without enrollments ({len(candidates)}) ---")
    for c in candidates:
        print(f"{c.user.id} - {c.user.get_full_name()} - {c.user.email}")

# --- Reports ---
print_candidates("active",     unenrolled.filter(user__is_active=True))
print_candidates("inactive",   unenrolled.filter(user__is_active=False))
print_candidates("verified",   unenrolled.filter(user__is_email_verified=True))
print_candidates("unverified", unenrolled.filter(user__is_email_verified=False))
"""
exec(code3)

code4 = r"""
from identity.models import Candidate

total_verified = Candidate.objects.filter(user__is_email_verified=True).count()
verified_and_logged_in = Candidate.objects.filter(
    user__is_email_verified=True,
    user__last_login__isnull=False,
).count()

print(f"Total verified: {total_verified}")
print(f"Verified and have logged in: {verified_and_logged_in}")
"""
exec(code4)

code5 = r"""
from identity.models import Candidate
anomalous = Candidate.objects.filter(
    user__last_login__isnull=False,
    user__is_email_verified=False,
).select_related('user')

for c in anomalous:
    print(f"{c.user.id} - {c.user.get_full_name()} - {c.user.email}")
"""
exec(code5)

code6 = r"""
from django.db import transaction
from django.contrib.auth import get_user_model

from competition.models import Enrollment
from identity.models import Candidate
from vmlc.models import CandidateExamResult, Exam, ExamAccess

SCREENING_EXAM_ID = "e0981a32-2765-4654-a523-11c2fd4c9b60"

total_unverified = Candidate.objects.filter(user__is_email_verified=False).count()
unverified_and_logged_in = Candidate.objects.filter(
    user__is_email_verified=False,
    user__last_login__isnull=False,
).values_list("user_id", flat=True)

print(f"Total unverified: {total_unverified}")
print(f"Unverified and have logged in: {unverified_and_logged_in.count()}")

total_inactive = Candidate.objects.filter(user__is_active=False).count()
inactive_and_logged_in = Candidate.objects.filter(
    user__is_active=False,
    user__last_login__isnull=False,
).values_list("user_id", flat=True)

print(f"Total inactive: {total_inactive}")
print(f"Inactive and have logged in: {inactive_and_logged_in.count()}")


disabled_users_with_exam_results = CandidateExamResult.objects.filter(
    exam=SCREENING_EXAM_ID,
    candidate__user_id__in=unverified_and_logged_in
)

if len(disabled_users_with_exam_results) == 0:
    print("No disabled candidates with exam results")
else:
    for c in disabled_users_with_exam_results:
        print(f"{c.candidate.user.id} - {c.candidate.user.get_full_name()} - {c.candidate.user.email}")

"""
exec(code6)
