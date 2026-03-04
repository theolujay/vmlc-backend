code6 = r"""
from django.db import transaction
from django.contrib.auth import get_user_model

from competition.models import Enrollment, Competition # Added Competition
from identity.models import Candidate
from vmlc.models import ExamAccess

DRY_RUN = False
SCREENING_EXAM_ID = "e0981a32-2765-4654-a523-11c2fd4c9b60"
EXAM_ACCESS_STATUSES = [ExamAccess.Status.STARTED, ExamAccess.Status.SUBMITTED, ExamAccess.Status.EXPIRED]

User = get_user_model()

# 1. Find candidates who are inactive AND unverified
# 2. Filter these candidates to also have a CandidateExamResult for SCREENING_EXAM_ID
# 3. Filter these candidates to also have an ExamAccess record for SCREENING_EXAM_ID
#    with status STARTED or SUBMITTED or EXPIRED.

# Start with candidates who are inactive and unverified
candidates_base_queryset = Candidate.objects.filter(
    user__is_active=False,
    user__is_email_verified=False,
)

# Further filter for CandidateExamResult
candidates_with_exam_results = candidates_base_queryset.filter(
    results__exam_id=SCREENING_EXAM_ID
).distinct()

# Get candidate_ids that have ExamAccess with specific statuses for the SCREENING_EXAM_ID
candidate_ids_with_matching_exam_access = ExamAccess.objects.filter(
    exam_id=SCREENING_EXAM_ID,
    status__in=EXAM_ACCESS_STATUSES
).values_list('candidate__user_id', flat=True)

# Now filter the candidates_with_exam_results by these candidate_ids
# This queryset now contains candidates matching criteria 1-4
final_candidates = candidates_with_exam_results.filter(
    user__id__in=candidate_ids_with_matching_exam_access
).select_related('user')


print(f"Found {final_candidates.count()} candidates matching the specified criteria:")

# Get the first active competition
active_competition = Competition.objects.filter(status=Competition.Status.ACTIVE).first()
if not active_competition:
    print("No active competition found.")
else:
    print(f"Checking enrollment and updating candidates for active competition: {active_competition.name} (Edition: {active_competition.edition})")

if DRY_RUN:
    print("\n--- DRY RUN MODE: No changes will be committed to the database ---")
else:
    print("\n --- LIVE RUN MODE: Changes will be commited to the database ---")
if final_candidates.count() == 0:
    print("No candidates found with the specified conditions.")
else:
    for candidate in final_candidates:
        try:
            with transaction.atomic():
                # 1. Ensure enrollment in the active competition
                enrollment, created_enrollment = Enrollment.objects.get_or_create(
                    candidate=candidate,
                    competition=active_competition,
                    defaults={'status': Enrollment.Status.ACTIVE}
                )
                enrollment_status_msg = "Created new enrollment" if created_enrollment else "Already enrolled"

                # 2. Mark as is_email_verified=True
                candidate.user.is_email_verified = True
                # 3. Mark as is_active=True
                candidate.user.is_active = True
                candidate.user.save()

                print(
                    f"Processed Candidate ID: {candidate.pk}, "
                    f"Name: {candidate.user.get_full_name()}, "
                    f"Email: {candidate.user.email}, "
                    f"Old Active: {not candidate.user.is_active}, " # Show old state for clarity
                    f"Old Verified Email: {not candidate.user.is_email_verified}, " # Show old state for clarity
                    f"New Active: {candidate.user.is_active}, "
                    f"New Verified Email: {candidate.user.is_email_verified}, "
                    f"Enrollment: {enrollment_status_msg}"
                )
                if DRY_RUN:
                    transaction.set_rollback(True)
        except Exception as e:
            print(f"Error processing candidate {candidate.pk} ({candidate.user.email}): {e}")
"""
exec(code6)
