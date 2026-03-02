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
    CowrywiseKidProfile,
)
from vmlc.models import (
    CandidateExamResult,
    Exam,
)
from comms.models import (
    HelpdeskThread,
    PublicSupportRequest,
    ThreadMessage,
    MessageRead,
)
from .tasks import (
    generate_stats_overview_task,
    # update_staff_dashboard_cache_task,
)
from competition.models import Competition, Stage, RankingSnapshot, Enrollment


from vmlc.v2.utils import CacheKeys


def refresh_stats_overview_cache(sender=None, _instance=None, **kwargs):
    """
    Invalidates the cache for all decentralized stats and triggers regeneration.
    """
    keys_to_delete = [
        CacheKeys.STATS_CANDIDATES,
        CacheKeys.STATS_STAFF,
        CacheKeys.STATS_EXAMS,
        CacheKeys.STATS_COMPETITION,
        CacheKeys.STATS_HELPDESK,
        CacheKeys.STATS_FUNNEL,
        CacheKeys.STATS_GEOGRAPHICS,
        "stats_overview",  # legacy
    ]
    cache.delete_many(keys_to_delete)
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
        cache.set("user_list_version", 2, timeout=84000)


# Specific invalidations for dashboards when data changes.
def invalidate_dashboard_on_change(sender, instance, **kwargs):
    """Specific invalidations for dashboards when data changes."""
    from vmlc.v2.utils import (
        invalidate_candidate_cache,
        invalidate_staff_dashboard,
        invalidate_score_boards,
    )

    if isinstance(instance, Candidate):
        invalidate_candidate_cache(instance.pk, user_id=instance.user_id)
        invalidate_staff_dashboard()
    elif isinstance(instance, Staff):
        invalidate_staff_dashboard()
    elif isinstance(instance, CowrywiseKidProfile):
        invalidate_candidate_cache(
            instance.candidate_id, user_id=instance.candidate.user_id
        )
        invalidate_staff_dashboard()
    elif isinstance(instance, CandidateExamResult):
        invalidate_candidate_cache(
            instance.candidate_id, user_id=instance.candidate.user_id
        )
        invalidate_staff_dashboard()
    elif isinstance(instance, (Competition, Stage, RankingSnapshot, Enrollment)):
        invalidate_staff_dashboard()
        invalidate_score_boards()
    elif isinstance(instance, RankingSnapshot):
            invalidate_score_boards(exam_id=instance.exam.id)
    elif isinstance(instance, Exam):
        from vmlc.v2.tasks import invalidate_exam_related_caches_task
        from django.db import transaction

        transaction.on_commit(
            lambda: invalidate_exam_related_caches_task.delay(str(instance.id))
        )
        # Notify candidates if it's a new exam
        # TODO: repurpose or discard this. It "notifies" candidates of a newly created exam
        # that'll most definitely have exam.status == "draft", which isn't desired.
        # if kwargs.get("created", False):
        #     from comms.tasks import notify_candidates_about_exam_task

        #     transaction.on_commit(
        #         lambda: notify_candidates_about_exam_task.delay(
        #             instance.id, "scheduled"
        #         )
        #     )


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
    # user_from_db = User.objects.filter(pk=user.pk).values("last_login").first()
    # TODO: consider using this `is_first_login` to prompt users to change their passwods on the frontend
    # is_first_login = user_from_db and user_from_db["last_login"] is None

    # Set email as verified on login if not already verified.
    # This effectively verifies the email on the first successful login,
    # since "magic login link" is sent to users upon registration that's
    # used to log them in for the first time using an included generated password in the email.
    if not user.is_email_verified:
        user.is_email_verified = True
        user.save(update_fields=["is_email_verified"])

    # TODO: update enrollment.status to ACTIVE from PENDING (during registration)
    # when a candidate logs in for the first time
    # TODO: implement a more refined way of handling this
    if (
        hasattr(user, "candidate_profile")
        and user.is_active
    ):
        Enrollment.objects.filter(candidate=user.candidate_profile, status=Enrollment.Status.PENDING).update(
            status=Enrollment.Status.ACTIVE
        )


# Invalidate stats cache on changes to relevant models.
# This is a broad approach, but ensures data freshness for the overview.

models_to_watch = [
    User,
    Candidate,
    Staff,
    UserVerification,
    PreRegUser,
    CandidateExamResult,
    Exam,
    Competition,
    Stage,
    RankingSnapshot,
    Enrollment,
    HelpdeskThread,
    PublicSupportRequest,
    ThreadMessage,
    MessageRead,
    CowrywiseKidProfile,
]
for model in models_to_watch:
    post_save.connect(refresh_stats_overview_cache, sender=model)
    post_delete.connect(refresh_stats_overview_cache, sender=model)

    # Connect user list invalidation for relevant models
    if model in [
        User,
        Staff,
        Candidate,
        PreRegUser,
        UserVerification,
        Exam,
        Competition,
    ]:
        post_save.connect(invalidate_user_list_cache, sender=model)
        post_delete.connect(invalidate_user_list_cache, sender=model)

    # Dashboard-specific invalidation
    if model in [
        Candidate,
        Staff,
        CandidateExamResult,
        Competition,
        Stage,
        RankingSnapshot,
        Enrollment,
        Exam,
        CowrywiseKidProfile,
    ]:
        post_save.connect(invalidate_dashboard_on_change, sender=model)
        post_delete.connect(invalidate_dashboard_on_change, sender=model)
