from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User
from .utils.auth import send_otp_to_email



@receiver(post_save, sender=User)
def send_otp_on_registration(
    sender, instance, created, **kwargs
):
    if created and not instance.is_email_verified:
        send_otp_to_email(instance)
