import logging
from typing import Optional, Tuple, List

from django.conf import settings
from django.template.loader import render_to_string

from identity.models import User, PreRegUser
from comms.models import PublicSupportRequest, SupportChatThread, ThreadMessage
from vmlc.models import FeatureFlag

logger = logging.getLogger(__name__)


def create_email_html(
    subject: str, message: str, otp: Optional[str] = None, otp_message: Optional[str] = None
) -> str:
    """
    Renders the email HTML template with the provided context.
    """
    context = {
        "subject": subject,
        "message": message,
        "otp": otp,
        "otp_message": otp_message,
    }
    return render_to_string("comms/email_base.html", context)


def send_system_email(
    subject: str,
    message: str,
    recipient_email: str,
    html_message: Optional[str] = None,
) -> None:
    """
    Helper function to queue a system email.
    """
    try:
        from comms.tasks import send_mail_task

        if not html_message:
            html_message = create_email_html(subject=subject, message=message)

        send_mail_task.delay(
            subject=subject,
            message=message,
            recipient_list=[recipient_email],
            html_message=html_message,
        )
    except Exception as e:
        logger.error(f"Failed to queue email to {recipient_email}: {str(e)}")


def build_registration_welcome_email(
    user: User,
    generated_password: Optional[str] = None,
) -> Tuple[str, str]:
    login_url = settings.FRONTEND_LOGIN
    password_msg = ""

    if generated_password:
        password_msg = (
            f"Your generated password is: {generated_password}\n"
            "Please use 'Forgot Password' to set your own password.\n\n"
        )

    subject = "Welcome to Verboheit MLC!"

    if hasattr(user, "candidate_profile"):
        message = (
            f"Hi {user.first_name},\n\n"
            "You have successfully registered for the Verboheit Mathematics League Competition.\n\n"
            "We're excited to have you participate and compete with students across regions.\n\n"
            f"{password_msg}"
            f"Login here: {login_url}\n\n"
            "Best regards,\n"
            "The VMLC Team"
        )

    elif hasattr(user, "staff_profile"):
        message = (
            f"Hi {user.first_name},\n\n"
            "Thank you for volunteering to support the Verboheit Mathematics League Competition.\n\n"
            "We appreciate your willingness to contribute to the success of this initiative.\n\n"
            f"{password_msg}"
            f"Login here: {login_url}\n\n"
            "Best regards,\n"
            "The VMLC Team"
        )

    else:
        raise ValueError("User must have either candidate or staff profile")

    return subject, message


def build_pre_registration_email(
    user: PreRegUser,
) -> Tuple[str, str]:
    registration_url = f"{settings.LANDING_BASE_URL}/register"
    interest_type = user.interest_type

    feature_flag_key = (
        "candidate_registration"
        if interest_type == "candidate"
        else "staff_registration"
    )

    if FeatureFlag.get_bool(feature_flag_key, default=False):
        subject = "Registration Is Now Open - Verboheit MLC"
        message = (
            f"Hi {user.full_name},\n\n"
            f"You previously expressed interest in the Verboheit Mathematics League Competition "
            f"as a {interest_type}.\n\n"
            "Registration is now open. You can complete your registration using the link below:\n\n"
            f"{registration_url}\n\n"
            "We look forward to having you on board.\n\n"
            "Best regards,\n"
            "The Verboheit MLC Team"
        )
    else:
        subject = "Your Interest Has Been Recorded - Verboheit MLC"
        message = (
            f"Hi {user.full_name},\n\n"
            f"Thank you for expressing interest in the Verboheit Mathematics League Competition "
            f"as a {interest_type}.\n\n"
            "We'll notify you once registration opens.\n\n"
            f"If you have any questions, contact us at {settings.SUPPORT_EMAIL}.\n\n"
            "Best regards,\n"
            "The Verboheit MLC Team"
        )

    return subject, message


def build_support_confirmation_email(
    inquiry: PublicSupportRequest,
) -> Tuple[str, str]:
    subject = "Thank You for Supporting Verboheit"
    support_label = inquiry.get_type_display()

    message = (
        f"Dear {inquiry.full_name},\n\n"
        "Thank you for reaching out to support the Verboheit Mathematics League Competition.\n\n"
        f"We've received your inquiry regarding {support_label} support. "
        "A member of our team will review your message and follow up if necessary.\n\n"
        "We truly appreciate your interest in supporting this initiative.\n\n"
        "Best regards,\n"
        "The Verboheit MLC Team"
    )

    return subject, message


def build_support_notification_email(
    inquiry: PublicSupportRequest,
) -> Tuple[str, str]:
    support_label = inquiry.get_type_display()
    subject = f"New Support Inquiry: {support_label}"

    message = (
        f"A new support inquiry has been received.\n\n"
        f"Name: {inquiry.full_name}\n"
        f"Email: {inquiry.email}\n"
        f"Phone: {inquiry.phone}\n"
        f"Organization: {inquiry.organization}\n"
        f"Support Type: {support_label}\n\n"
        f"Message:\n{inquiry.message}\n\n"
        "Please review and follow up."
    )

    return subject, message


def build_chat_thread_notification_email(
    thread: SupportChatThread,
) -> Tuple[str, str]:
    priority_label = thread.get_priority_display()
    subject = f"[{priority_label}] New Support Chat Thread: {thread.user.email if thread.user else 'Anonymous'}"

    message = (
        f"A new authenticated support thread has been received.\n\n"
        f"User: {thread.user.get_full_name() if thread.user else 'Anonymous'}\n"
        f"Email: {thread.user.email if thread.user else 'N/A'}\n"
        f"Priority: {priority_label}\n"
        f"Status: {thread.get_status_display()}\n\n"
        f"Message:\n{thread.message}\n\n"
        "Please review and follow up."
    )

    return subject, message


def build_chat_thread_reply_email(
    message: ThreadMessage,
) -> Tuple[str, str]:
    thread = message.thread
    subject = f"Re: Support Chat Thread #{thread.id}"

    reply_content = (
        f"A new reply has been posted to your support thread regarding: {thread.message[:50]}...\n\n"
        f"Reply:\n{message.text}\n\n"
        f"You can view the full conversation and reply on your dashboard.\n\n"
        "Best regards,\n"
        "The Verboheit MLC Team"
    )

    return subject, reply_content


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
            f"Your generated password is: \n"
            f"{generated_password}\n"
            f"Please use 'Forgot Password' to set your own password.\n"
        )
    try:
        from comms.tasks import send_mail_task

        if isinstance(user, User):
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

            if feature_flag_key is not None and FeatureFlag.get_bool(
                feature_flag_key, default=False
            ):
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
