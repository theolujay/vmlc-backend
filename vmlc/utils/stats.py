from ..models import Candidate, Staff
from .user import get_user_status_counts


def generate_stats_overview_data():
    """
    Generates and returns a dictionary containing the full stats overview.
    """
    candidate_stats = _get_candidate_stats()
    staff_stats = _get_staff_stats()

    data = {
        "candidates": candidate_stats,
        "staff": staff_stats,
    }
    return data
 
def _get_candidate_stats() -> dict:
    """Helper to get candidate statistics."""
    registered_candidates_qs = Candidate.objects.filter(user__is_email_verified=True)
    return get_user_status_counts(registered_candidates_qs, "candidate")
 
def _get_staff_stats() -> dict:
    """Helper to get staff statistics."""
    registered_staff_qs = Staff.objects.filter(user__is_email_verified=True)
    return get_user_status_counts(registered_staff_qs, "staff")
