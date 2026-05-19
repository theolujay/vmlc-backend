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
from competition.models import Enrollment
from competition.signals import refresh_stats_overview_cache


def invalidate_user_list_cache(sender=None, _instance=None, **kwargs):
    """Invalidates the user list view cache by incrementing the version."""
    try:
        cache.incr("user_list_version")
    except ValueError:
        cache.set("user_list_version", 2, timeout=84000)


@receiver(user_logged_in, sender=User)
def user_logged_in_receiver(sender, request, user, **kwargs):
    """Handle post-login tasks: stats refresh, email verification, enrollment activation."""
    refresh_stats_overview_cache()
    if not user.is_email_verified:
        user.is_email_verified = True
        user.save(update_fields=["is_email_verified"])

    if hasattr(user, "candidate_profile") and user.is_active:
        Enrollment.objects.filter(
            candidate=user.candidate_profile, status=Enrollment.Status.PENDING
        ).update(status=Enrollment.Status.ACTIVE)


models_to_watch = [
    User,
    Staff,
    Candidate,
    PreRegUser,
    UserVerification,
]
for model in models_to_watch:
    post_save.connect(invalidate_user_list_cache, sender=model)
    post_delete.connect(invalidate_user_list_cache, sender=model)
