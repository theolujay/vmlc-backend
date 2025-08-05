"""
Auth-related utility functions.
"""

import logging
import random
from datetime import timedelta

from django.core.mail import send_mail
from django.utils import timezone
from django.conf import settings
from rest_framework import serializers

from ..models import EmailOTP
from ..tasks import send_otp_to_email_task

logger = logging.getLogger(__name__)


def generate_otp() -> str:
    """
    Generates a 6-digit OTP.
    """
    otp = str(random.randint(100000, 999999))
    logger.debug("OTP generated successfully")
    return otp

def can_resend_otp(user, cooldown_minutes: int = 2) -> tuple[bool, int]:
    """
    Check if user can resend OTP based on cooldown period.
    
    Args:
        user: User object
        cooldown_minutes: Minimum minutes between OTP requests
        
    Returns:
        tuple: (can_resend: bool, seconds_remaining: int)
    """
    try:
        # Get the most recent OTP for this user
        latest_otp = EmailOTP.objects.filter(user=user).order_by('-created_at').first()
        
        if not latest_otp:
            logger.debug(f"No previous OTP found for user {user.id}, can resend")
            return True, 0
        
        # Calculate time since last OTP
        time_since_last = timezone.now() - latest_otp.created_at
        cooldown_period = timedelta(minutes=cooldown_minutes)
        
        if time_since_last >= cooldown_period:
            logger.debug(f"Cooldown period passed for user {user.id}, can resend")
            return True, 0
        else:
            seconds_remaining = int((cooldown_period - time_since_last).total_seconds())
            logger.info(f"User {user.id} must wait {seconds_remaining} seconds before resending OTP")
            return False, seconds_remaining
            
    except Exception as e:
        logger.error(f"Error checking OTP resend eligibility for user {user.id}: {str(e)}")
        # In case of error, allow resend to avoid blocking users
        return True, 0

def send_otp_to_email(user, is_resend: bool = False):
    """
    Generates and sends OTP to user's email address.
    
    Args:
        user: User object with email attribute
        is_resend: Whether this is a resend request
    """
    try:
        # Check rate limiting for resends
        if is_resend:
            can_resend, seconds_remaining = can_resend_otp(user)
            if not can_resend:
                logger.warning(f"OTP resend blocked for user {user.id} - {seconds_remaining}s remaining")
                raise serializers.ValidationError(
                    f"Please wait {seconds_remaining} seconds before requesting another OTP."
                )
        
        # Invalidate any existing OTPs for this user
        EmailOTP.objects.filter(user=user, expires_at__gt=timezone.now()).update(
            expires_at=timezone.now()
        )
        logger.info(f"Invalidated existing OTPs for user {user.id}")
        
        # Generate new OTP
        otp = generate_otp()
        expiration = timezone.now() + timedelta(minutes=10)
        
        # Save to database
        EmailOTP.objects.create(
            user=user,
            otp=otp,
            created_at=timezone.now(),
            expires_at=expiration
        )
        
        action = "resent" if is_resend else "created"
        logger.info(f"OTP {action} for user {user.id} (masked: {user.email[:3]}***)")

        # Send email
        subject = "Your OTP Code" + (" (Resent)" if is_resend else "")
        message = f"Your OTP code is {otp}. It expires in 10 minutes."
        
        # send_mail(
        #     subject=subject,
        #     message=message,
        #     from_email="no-reply@verboheit.org",
        #     recipient_list=[user.email],
        #     fail_silently=False,
        # )

        send_otp_to_email_task.delay(
            subject=subject,
            message=message,
            recipient_list=[user.email],
        )
        
        logger.info(f"OTP email {action} successfully to user {user.id}")
        
    except serializers.ValidationError:
        # Re-raise validation errors (rate limiting)
        raise
    except Exception as e:
        action = "resending" if is_resend else "sending"
        logger.error(f"Failed {action} OTP email to user {user.id}: {str(e)}")
        raise

def resend_otp_to_email(user):
    """
    Convenience function specifically for resending OTP.
    
    Args:
        user: User object with email attribute
    """
    send_otp_to_email(user, is_resend=True)

def send_password_change_otp(user):
    """
    Sends OTP specifically for password change requests.
    
    Args:
        user: User object with email attribute
    """
    try:
        # Check rate limiting
        can_resend, seconds_remaining = can_resend_otp(user)
        if not can_resend:
            logger.warning(f"Password change OTP blocked for user {user.id} - {seconds_remaining}s remaining")
            raise serializers.ValidationError(
                f"Please wait {seconds_remaining} seconds before requesting another OTP."
            )
        
        # Invalidate existing OTPs
        EmailOTP.objects.filter(user=user, expires_at__gt=timezone.now()).update(
            expires_at=timezone.now()
        )
        logger.info(f"Invalidated existing OTPs for password change - user {user.id}")
        
        # Generate new OTP
        otp = generate_otp()
        expiration = timezone.now() + timedelta(minutes=10)
        
        # Save to database
        EmailOTP.objects.create(
            user=user,
            otp=otp,
            created_at=timezone.now(),
            expires_at=expiration
        )
        
        logger.info(f"Password change OTP created for user {user.id}")

        # Send email with password-specific message
        send_mail(
            subject="Password Change Verification",
            message=(
                f"Your verification code for password change is {otp}. "
                f"This code expires in 10 minutes. "
                f"If you didn't request this, please ignore this email."
            ),
            from_email="no-reply@verboheit.org",
            recipient_list=[user.email],
            fail_silently=False,
        )
        
        logger.info(f"Password change OTP email sent to user {user.id}")
        
    except serializers.ValidationError:
        # Re-raise validation errors (rate limiting)
        raise
    except Exception as e:
        logger.error(f"Failed sending password change OTP to user {user.id}: {str(e)}")
        raise

def verify_otp_for_password_change(user, otp_code):
    """
    Verify OTP for password change and mark it as used.
    
    Args:
        user: User object
        otp_code: OTP code to verify
        
    Returns:
        bool: True if OTP is valid, False otherwise
    """
    try:
        # Find valid OTP for this user
        otp_record = EmailOTP.objects.filter(
            user=user,
            otp=otp_code,
            expires_at__gt=timezone.now()
        ).first()
        
        if not otp_record:
            logger.warning(f"Invalid/expired OTP attempt for password change - user {user.id}")
            return False
        
        # Mark OTP as used by expiring it
        otp_record.expires_at = timezone.now()
        otp_record.save()
        
        logger.info(f"OTP verified successfully for password change - user {user.id}")
        return True
        
    except Exception as e:
        logger.error(f"Error verifying password change OTP for user {user.id}: {str(e)}")
        return False