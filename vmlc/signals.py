from django.contrib.auth.signals import user_logged_in
from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from identity.models import (
    PreRegUser,
    User,
    Candidate,
    Staff,
    UserVerification,
)
from vmlc.models import (
    CandidateExamResult,
    Exam,
)
from .tasks import (
    generate_stats_overview_task,
    update_staff_dashboard_cache_task,
)


def refresh_stats_overview_cache(sender=None, _instance=None, **kwargs):
    """
    Invalidates the cache for the stats overview and triggers regeneration.
    """
    cache.delete("stats_overview")
    cache.delete("registration_metrics")
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


# Specific invalidations for dashboards when data changes.
def invalidate_dashboard_on_change(sender, instance, **kwargs):
    """Specific invalidations for dashboards when data changes."""
    from vmlc.v2.utils import invalidate_candidate_cache, invalidate_staff_dashboard, invalidate_league_leaderboard
    from competition.models import Competition, Stage, RankingSnapshot, Enrollment
    
    if isinstance(instance, Candidate):
        invalidate_candidate_cache(instance.pk, user_id=instance.user_id)
        invalidate_staff_dashboard()
    elif isinstance(instance, Staff):
        invalidate_staff_dashboard()
    elif isinstance(instance, CandidateExamResult):
        invalidate_candidate_cache(instance.candidate_id, user_id=instance.candidate.user_id)
        invalidate_staff_dashboard()
    elif isinstance(instance, (Competition, Stage, RankingSnapshot, Enrollment)):
        invalidate_staff_dashboard()
        invalidate_league_leaderboard()
    elif isinstance(instance, Exam):
        from vmlc.v2.tasks import invalidate_exam_related_caches_task
        from django.db import transaction
        transaction.on_commit(lambda: invalidate_exam_related_caches_task.delay(str(instance.id)))


@receiver(user_logged_in, sender=User)
def user_logged_in_receiver(sender, request, user, **kwargs):
    """
    Handles post-login tasks:
    - Invalidates stats cache.
    - Sets email as verified on login if not already verified.
    - Updates dashboard caches for non-deactivated users.
    """
    refresh_stats_overview_cache()

    # Accurately identify first login by checking the database value
    # before it was potentially updated by Django's update_last_login receiver.
    user_from_db = User.objects.filter(pk=user.pk).values("last_login").first()
    # TODO: consider using this `is_first_login` to prompt users to change their passwods on the frontend
    is_first_login = user_from_db and user_from_db["last_login"] is None

    # Set email as verified on login if not already verified.
    # This effectively verifies the email on the first successful login.
    if not user.is_email_verified:
        user.is_email_verified = True
        user.save(update_fields=["is_email_verified"])

    # Update dashboard caches for verified users.
    # We ensure these are triggered for newly verified users as well.
    if (
        hasattr(user, "staff_profile")
        and user.is_email_verified
        and user.staff_profile.is_active
    ):
        update_staff_dashboard_cache_task.delay(user.id)


# Invalidate stats cache on changes to relevant models.
# This is a broad approach, but ensures data freshness for the overview.
from competition.models import Competition, Stage, RankingSnapshot, Enrollment
models_to_watch = [User, Candidate, Staff, UserVerification, PreRegUser, CandidateExamResult, Exam, Competition, Stage, RankingSnapshot, Enrollment]
for model in models_to_watch:
    post_save.connect(refresh_stats_overview_cache, sender=model)
    post_delete.connect(refresh_stats_overview_cache, sender=model)

    # Connect user list invalidation for relevant models
    if model in [User, Staff, Candidate, PreRegUser, UserVerification, Exam, Competition]:
        post_save.connect(invalidate_user_list_cache, sender=model)
        post_delete.connect(invalidate_user_list_cache, sender=model)

    # Dashboard-specific invalidation
    if model in [Candidate, Staff, CandidateExamResult, Competition, Stage, RankingSnapshot, Enrollment, Exam]:
        post_save.connect(invalidate_dashboard_on_change, sender=model)
        post_delete.connect(invalidate_dashboard_on_change, sender=model)
