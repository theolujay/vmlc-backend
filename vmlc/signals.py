from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from .models import User
from .tasks import send_otp_on_registration_task

@receiver(user_logged_in, sender=User)
def user_logged_in_receiver(sender, request, user, **kwargs):
    """
    Set is_email_verified to True on first login for users who were invited by
    another staff member (that typically has manager or superadmin roles).
    """
    if not user.is_email_verified:
        profile = None
        if hasattr(user, "staff_profile"):
            profile = user.staff_profile
        elif hasattr(user, "candidate_profile"):
            profile = user.candidate_profile

        if profile and profile.created_by is not None:
            user.is_email_verified = True
            user.save(update_fields=["is_email_verified"])
