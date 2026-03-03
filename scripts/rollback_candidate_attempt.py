code = r'''
import os
import django

# Set up Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.db import transaction
from django.db.models import Q
from identity.models import Candidate
from vmlc.models import Exam, CandidateExamResult, ExamAccess
from competition.models import (
    LeagueLeaderboardEntry,
    RankingSnapshotEntry,
    EnrollmentStageProgress,
    StageExam
)
from vmlc.v2.utils import invalidate_candidate_cache, invalidate_exam_cache

# --- CONFIGURATION ---
EXAM_ID = "e0981a32-2765-4654-a523-11c2fd4c9b60"
CANDIDATE_EMAILS = [
    "candidate10.vmlc@mailsac.com",
    "candidate9.vmlc@mailsac.com",
    "candidate9.vmlc@mailsac.com",
]
# ---------------------

def find_candidates_with_expired_exam_access(exam_id):
    """
    Finds and returns emails of candidates whose ExamAccess for the given exam ID
    is either explicitly marked as EXPIRED or has passed its deadline.
    """
    from django.utils import timezone
    now = timezone.now()

    expired_access = ExamAccess.objects.filter(
        exam_id=exam_id
    ).filter(
        Q(status=ExamAccess.Status.EXPIRED) |
        Q(deadline__lt=now, status=ExamAccess.Status.STARTED)
    ).select_related('candidate__user')

    emails = list(expired_access.values_list('candidate__user__email', flat=True))

    if emails:
        print(f"Found {len(emails)} candidates with expired access for Exam {exam_id}.")
    else:
        print(f"No candidates with expired access found for Exam {exam_id}.")

    return emails
def rollback_attempts(exam_id, emails):
    try:
        exam = Exam.objects.select_related('competition_slot__competition_stage').get(id=exam_id)
    except (Exam.DoesNotExist, ValueError):
        print(f"Error: Exam with ID '{exam_id}' not found.")
        return

    candidates = Candidate.objects.filter(user__email__in=emails).select_related('user')
    found_emails = list(candidates.values_list('user__email', flat=True))
    missing = set(emails) - set(found_emails)

    if missing:
        print(f"Warning: No candidates found for: {', '.join(missing)}")

    if not candidates.exists():
        print("No valid candidates found. Aborting.")
        return

    print(f"Rolling back attempts for {len(candidates)} candidates on exam: {exam.title}")

    try:
        with transaction.atomic():
            # 1. Delete CandidateExamResult (CASCADEs to CandidateAnswer)
            results_deleted, _ = CandidateExamResult.objects.filter(
                exam=exam,
                candidate__in=candidates
            ).delete()

            # 2. Reset ExamAccess (to allow retake)
            # We keep face_capture but reset status and timing
            access_updated = ExamAccess.objects.filter(
                exam=exam,
                candidate__in=candidates
            ).update(
                status=ExamAccess.Status.PENDING,
                started_at=None,
                deadline=None,
                submitted_at=None
            )

            # 3. Clear Competition Ranking Entries for this specific exam
            rankings_deleted, _ = RankingSnapshotEntry.objects.filter(
                ranking_snapshot__exam=exam,
                candidate__in=candidates
            ).delete()

            # 4. Clear League Leaderboard entries
            # Since these are cumulative, we remove them so they get recalculated
            # (or stay empty until the next attempt is scored)
            lb_entries_deleted, _ = LeagueLeaderboardEntry.objects.filter(
                candidate__in=candidates
            ).delete()

            # 5. Revert EnrollmentStageProgress if it was COMPLETED
            # If the exam belongs to a stage, and the candidate completed that stage,
            # we move them back to IN_PROGRESS.
            stage_progress_updated = 0
            if exam.competition_slot:
                stage = exam.competition_slot.competition_stage
                stage_progress_updated = EnrollmentStageProgress.objects.filter(
                    enrollment__candidate__in=candidates,
                    stage=stage,
                    status=EnrollmentStageProgress.Status.COMPLETED
                ).update(
                    status=EnrollmentStageProgress.Status.IN_PROGRESS,
                    completed_at=None
                )

            # 6. Cache Invalidation
            for candidate in candidates:
                invalidate_candidate_cache(candidate.pk, candidate.user.id)
            invalidate_exam_cache(exam.id)

            print("\n--- ROLLBACK SUCCESSFUL ---")
            print(f"Exam Result records deleted: {results_deleted}")
            print(f"Exam Access records reset:   {access_updated}")
            print(f"Ranking entries deleted:     {rankings_deleted}")
            print(f"Leaderboard entries cleared: {lb_entries_deleted}")
            print(f"Stage progress records reset: {stage_progress_updated}")
            print("\nCaches have been invalidated. Candidates can now retake the exam.")

    except Exception as e:
        print(f"CRITICAL ERROR during rollback: {e}")
        # transaction.atomic() handles the rollback automatically on exception

# if __name__ == "__main__":
if EXAM_ID == "YOUR_EXAM_ID_HERE":
    print("Usage: Edit EXAM_ID and CANDIDATE_EMAILS in the script first.")
else:
    candidate_emails = find_candidates_with_expired_exam_access(EXAM_ID)
    print(candidate_emails)
    # rollback_attempts(EXAM_ID, CANDIDATE_EMAILS)
    rollback_attempts(EXAM_ID, candidate_emails)
'''
exec(code)

code2 = r"""
from django.contrib.auth import get_user_model

User = get_user_model()

def _normalize_phone(phone):
    if not phone:
        return ""
    if phone.startswith("0"):
        return phone
    if phone.startswith("+234"):
        return "0" + phone[1:]
    return phone

emails = [
    'akinolarofiatadekilekun@gmail.com',
    'bmhsagbowa1@gmail.com',
    'physicistopeyemi@gmail.com',
    'mailstojayden1@gmail.com',
    'adedejiayomide780@gmail.com',
    'honeylandschoolisolo@gmail.com',
    'preciousonyemachukwu@gmail.com',
    'mcibru2016@gmail.com',
    'lekkyroil@gmail.com',
    'itzkorede1@gmail.com',
]

for user in User.objects.filter(email__in=emails):
    print(user.get_full_name(), "-", user.email, "-", _normalize_phone(user.phone))
"""
exec(code2)
