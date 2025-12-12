from django.contrib.auth.signals import user_logged_in
from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import (
    User,
    Candidate,
    Staff,
    UserVerification,
    CandidateScore,
    Exam,
)
from .tasks import (
    generate_stats_overview_task,
    update_candidate_dashboard_cache_task,
    update_staff_dashboard_cache_task,
)


def refresh_stats_overview_cache(sender=None, _instance=None, **kwargs):
    """
    Invalidates the cache for the stats overview and triggers regeneration.
    """
    cache.delete("stats_overview")
    cache.delete_pattern("user_list_view_*")
    generate_stats_overview_task.delay()


def invalidate_user_list_cache(sender=None, _instance=None, **kwargs):
    """Invalidates the user list view cache by incrementing the version."""
    # It's possible the key doesn't exist, so we handle the ValueError.
    try:
        cache.incr("user_list_version")
    except ValueError:
        # If the key is missing, we set it. The next request will generate a new cache.
        cache.set("user_list_version", 2)


@receiver(user_logged_in, sender=User)
def user_logged_in_receiver(sender, request, user, **kwargs):
    """
    Handles post-login tasks:
    - Invalidates stats cache.
    - Updates dashboard caches for verified users.
    - Sets email as verified on first login for invited users.
    """
    refresh_stats_overview_cache()

    if (
        hasattr(user, "staff_profile")
        and user.is_email_verified
        and user.staff_profile.is_user_verified
    ):
        update_staff_dashboard_cache_task.delay(user.id)
    if (
        hasattr(user, "candidate_profile")
        and user.is_email_verified
        and user.candidate_profile.is_user_verified
    ):
        update_candidate_dashboard_cache_task.delay(user.id)
    if user.last_login is None and not user.is_email_verified:
        profile = None
        if hasattr(user, "staff_profile"):
            profile = user.staff_profile
        elif hasattr(user, "candidate_profile"):
            profile = user.candidate_profile

        if profile and profile.created_by is not None:
            user.is_email_verified = True
            user.save(update_fields=["is_email_verified"])


# Invalidate stats cache on changes to relevant models.
# This is a broad approach, but ensures data freshness for the overview.
models_to_watch = [User, Candidate, Staff, UserVerification, CandidateScore, Exam]
for model in models_to_watch:
    post_save.connect(refresh_stats_overview_cache, sender=model)
    post_delete.connect(refresh_stats_overview_cache, sender=model)

    # Connect user list invalidation for relevant models
    if model in [User, Staff, Candidate, UserVerification, Exam]:
        post_save.connect(invalidate_user_list_cache, sender=model)
        post_delete.connect(invalidate_user_list_cache, sender=model)
