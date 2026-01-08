import logging
import string
import secrets
from datetime import timedelta
from typing import Tuple, Any

from django.conf import settings
from django.utils import timezone
from rest_framework import serializers

from ..models import EmailOTP, PreRegUser, User, FeatureFlag
from .email import create_email_html


logger = logging.getLogger(__name__)


def generate_password(length: int = 12) -> str:
    """
    Generates a secure random password that meets these criteria:
    - 8-32 characters long
    - At least 1 lowercase character (a-z)
    - At least 1 uppercase character (A-Z)
    - At least 1 number (0-9)
    - At least 1 special character (!@#$%^&*()_+-=[]{}|;:,.<>?)

    Args:
        length: Desired password length (default: 12)

    Returns:
        A secure random password as a string

    Raises:
        ValueError: If length is not between 8 and 32
    """

    if length < 8 or length > 32:
        raise ValueError("Password length must be between 8 and 32 characters")

    lowercase = string.ascii_lowercase  # a-z
    uppercase = string.ascii_uppercase  # A-Z
    digits = string.digits  # 0-9
    special = "!@#$%^&*()_+-=[]{}|;:,.<>?"
    all_characters = lowercase + uppercase + digits + special

    password = [
        secrets.choice(lowercase),
        secrets.choice(uppercase),
        secrets.choice(digits),
        secrets.choice(special),
    ]

    for _ in range(length - 4):
        password.append(secrets.choice(all_characters))

    secrets.SystemRandom().shuffle(password)

    return "".join(password)


def generate_otp(length: int = 6) -> str:
    """
    Generates a secure 6-digit OTP
    """
    digits = string.digits
    return "".join(secrets.choice(digits) for _ in range(length))


def can_resend_otp(user: User, cooldown_minutes: int = 2) -> Tuple[bool, int]:
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
        latest_otp: EmailOTP = (
            EmailOTP.objects.filter(user=user).order_by("-created_at").first()
        )

        if not latest_otp:
            logger.debug(f"No previous OTP found for user {user.id}, can resend")
            return True, 0

        # Calculate time since last OTP
        time_since_last: timedelta = timezone.now() - latest_otp.created_at
        cooldown_period: timedelta = timedelta(minutes=cooldown_minutes)

        if time_since_last >= cooldown_period:
            logger.debug(f"Cooldown period passed for user {user.id}, can resend")
            return True, 0

        seconds_remaining: int = int(
            (cooldown_period - time_since_last).total_seconds()
        )
        logger.info(
            f"User {user.id} must wait {seconds_remaining} seconds before resending OTP"
        )
        return False, seconds_remaining

    except Exception as e:
        logger.error(
            f"Error checking OTP resend eligibility for user {user.id}: {str(e)}"
        )
        # In case of error, allow resend to avoid blocking users
        return True, 0


def send_otp_to_email(user: User, is_resend: bool = False) -> None:
    """
    Generates and sends OTP to user's email address.

    Args:
        user: User object with email attribute
        is_resend: Whether this is a resend request
    """
    try:
        from ..tasks import send_mail_task

        # Check rate limiting for resends
        if is_resend:
            can_resend: bool
            seconds_remaining: int
            can_resend, seconds_remaining = can_resend_otp(user)
            if not can_resend:
                logger.warning(
                    f"OTP resend blocked for user {user.id} - {seconds_remaining}s remaining"
                )
                raise serializers.ValidationError(
                    f"Please wait {seconds_remaining} seconds before requesting another OTP."
                )

        # Invalidate any existing OTPs for this user
        EmailOTP.objects.filter(user=user, expires_at__gt=timezone.now()).update(
            expires_at=timezone.now()
        )
        logger.info(f"Invalidated existing OTPs for user {user.id}")

        # Generate new OTP
        otp: str = generate_otp()
        expiration: Any = timezone.now() + timedelta(minutes=10)

        # Save to database
        EmailOTP.objects.create(
            user=user, otp=otp, created_at=timezone.now(), expires_at=expiration
        )

        action: str = "resent" if is_resend else "created"
        logger.info(f"OTP {action} for user {user.id} (masked: {user.email[:3]}***)")

        # Send email
        subject: str = "Your OTP Code" + (" (Resent)" if is_resend else "")
        message: str = f"Your OTP code is {otp}. It expires in 10 minutes."
        html_message = create_email_html(subject=subject, message=message, otp=otp)

        send_mail_task.delay(
            subject=subject,
            message=message,
            recipient_list=[user.email],
            html_message=html_message,
        )

        logger.info(f"OTP email {action} successfully to user {user.id}")

    except serializers.ValidationError:
        # Re-raise validation errors (rate limiting)
        raise
    except Exception as e:
        action: str = "resending" if is_resend else "sending"
        logger.error(f"Failed {action} OTP email to user {user.id}: {str(e)}")
        raise


def resend_otp_to_email(user: User) -> None:
    """
    Convenience function specifically for resending OTP.

    Args:
        user: User object with email attribute
    """
    send_otp_to_email(user, is_resend=True)


def send_password_change_otp(user: User) -> None:
    """
    Sends OTP specifically for password change requests.

    Args:
        user: User object with email attribute
    """
    try:
        from ..tasks import send_mail_task

        # Check rate limiting
        can_resend: bool
        seconds_remaining: int
        can_resend, seconds_remaining = can_resend_otp(user)
        if not can_resend:
            logger.warning(
                f"Password change OTP blocked for user {user.id} - {seconds_remaining}s remaining"
            )
            raise serializers.ValidationError(
                f"Please wait {seconds_remaining} seconds before requesting another OTP."
            )

        # Invalidate existing OTPs
        EmailOTP.objects.filter(user=user, expires_at__gt=timezone.now()).update(
            expires_at=timezone.now()
        )
        logger.info(f"Invalidated existing OTPs for password change - user {user.id}")

        # Generate new OTP
        otp: str = generate_otp()
        expiration: Any = timezone.now() + timedelta(minutes=10)

        # Save to database
        EmailOTP.objects.create(
            user=user, otp=otp, created_at=timezone.now(), expires_at=expiration
        )

        logger.info(f"Password change OTP created for user {user.id}")

        # Send email with password-specific message
        subject = "Password Change Verification"
        message = (
            f"Your verification code for password change is {otp}. "
            f"This code expires in 10 minutes. "
            f"If you didn't request this, please ignore this email."
        )
        html_message = create_email_html(
            subject=subject,
            message=message,
            otp=otp,
            otp_message="...expires in 10 minutes.<br><br>If you didn't request this, please ignore this email.",
        )
        send_mail_task.delay(
            subject=subject,
            message=message,
            recipient_list=[user.email],
            html_message=html_message,
        )

        logger.info(f"Password change OTP email sent to user {user.id}")

    except serializers.ValidationError:
        # Re-raise validation errors (rate limiting)
        raise
    except Exception as e:
        logger.error(f"Failed sending password change OTP to user {user.id}: {str(e)}")
        raise


def verify_otp_for_password_change(user: User, otp_code: str) -> bool:
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
        otp_record: EmailOTP = EmailOTP.objects.filter(
            user=user, otp=otp_code, expires_at__gt=timezone.now()
        ).first()

        if not otp_record:
            logger.warning(
                f"Invalid/expired OTP attempt for password change - user {user.id}"
            )
            return False

        # Mark OTP as used by expiring it
        otp_record.expires_at = timezone.now()
        otp_record.save()

        logger.info(f"OTP verified successfully for password change - user {user.id}")
        return True

    except Exception as e:
        logger.error(
            f"Error verifying password change OTP for user {user.id}: {str(e)}"
        )
        return False


def send_welcome_email(user: User | PreRegUser, generated_password: str = None) -> None:
    """
    Sends a welcome email to the newly registered user.

    Args:
        user: User or PreRegUser object
        generated_password: Optional generated password for the user
    """
    login_url = f"{settings.FRONTEND_LOGIN}"
    registration_url = f"{settings.LANDING_BASE_URL}/register"
    subject = ""
    message = ""
    generated_password_msg = ""
    if generated_password is not None:
        generated_password_msg = (
            f"Your generated password is: {generated_password}\n"
            f"Please use 'Forgot Password' to set your own password.\n"
        )
    try:
        from ..tasks import send_mail_task

        if type(user) == User:
            subject: str = "Welcome to Verboheit MLC!"

            if hasattr(user, "candidate_profile"):
                message: str = (
                    f"Hi!\n\n"
                    f"Good to have you onboard, {user.first_name}. "
                    f"You have successfully registered for the next edition of the Verboheit Mathematics League Competition. "
                    f"An opportunity to journey with your mates far and near to compete against one another awaits you.\n\n"
                    f"Kindly follow the login link below to begin.\n\n"
                    f"{generated_password_msg}"
                    f"Login: {login_url}\n\n"
                    "Best regards,\n"
                    "The VMLC Team."
                )
            elif hasattr(user, "staff_profile"):
                message: str = (
                    f"Welcome onboard, {user.first_name},\n\n"
                    f"You have chosen to be a part of the Verboheit Mathematics League Competition."
                    f"Glad to have you volunteering to make this competition a success. We look forward "
                    f"to your contributions. First things first, please follow the link below to log in "
                    f"to get started.\n\n"
                    f"{generated_password_msg}"
                    f"Login: {login_url}\n\n"
                    "Looking forward to achieving great things together!\n\n"
                    "Best regards,\n"
                    "The VMLC Team."
                )
            logger.info(f"Welcome email sent successfully to user {user.id}")
        else:  # PreRegUser
            interest_type = user.interest_type
            feature_flag_key = None
            if interest_type == "candidate":
                feature_flag_key = "candidate_registration"
            else:
                feature_flag_key = "staff_registration"

            if (feature_flag_key is not None and FeatureFlag.get_bool(feature_flag_key, default=False)):
                subject = "Thanks for Your Interest in Verboheit MLC!"
                message = (
                    f"Hi {user.full_name},\n\n"
                    f"We get that you're interested in the Verboheit Mathematics League Competition "
                    f"as a {interest_type}.\n\n"
                    f"Great news! Registration is now open. You can complete your full registration "
                    f"by visiting the link below:\n\n"
                    f"Register: {registration_url}\n\n"
                    f"We look forward to having you participate in this year's competition.\n\n"
                    "Best regards,\n"
                    "The VMLC Team."
                )
            else:
                subject = "Your Interest at Verboheit MLC is Confirmed"
                message = (
                    f"Hi {user.full_name},\n\n"
                    f"Thank you for expressing interest in the Verboheit Mathematics League Competition "
                    f"as a {interest_type}.\n\n"
                    f"We've acknowledged your interest and will notify you via email as soon as "
                    f"full registration opens.\n\n"
                    f"In the meantime, feel free to reach out at {settings.SUPPORT_EMAIL} if you have any questions.\n\n"
                    "Best regards,\n"
                    "The VMLC Team."
                )
                
        send_mail_task.delay(
            subject=subject, message=message, recipient_list=[user.email]
        )

    except Exception as e:
        logger.error(f"Failed to send welcome email to user {user.id}: {str(e)}")
