import os
import logging

from django.utils import timezone
from django.conf import settings
from django.core.files import File
from django.core.cache import cache
from django.core.mail import send_mail
from celery import shared_task
from celery.exceptions import Retry

from vmlc.utils import generate_stats_overview_data

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="send_mail_task",
    max_retries=3,
    default_retry_delay=60,
    queue="comms",
)
def send_mail_task(self, subject, message, recipient_list, html_message=None):
    """
    Celery task to send an email asynchronously.

    It will automatically retry up to 3 times if it fails,
    with a 60-second delay between retries.
    """
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_list,
            fail_silently=False,
            html_message=html_message,
        )
        logger.info(f"Successfully sent email to {recipient_list}")
    except Exception as exc:
        logger.error(f"Failed to send email to {recipient_list}: {exc}")
        # The `self.retry` call will re-queue the task.
        # The `bind=True` and `max_retries` arguments in the decorator handle this automatically.
        raise self.retry(exc=exc, countdown=60)


@shared_task(
    bind=True,
    name="send_otp_on_registration_task",
    max_retries=3,
    default_retry_delay=60,
    queue="comms",
)
def send_otp_on_registration_task(self, user_id):
    """
    Celery task to send OTP to user on registration.
    """
    from identity.models import User
    from vmlc.utils.auth import send_otp_to_email

    try:
        user = User.objects.get(pk=user_id)
        send_otp_to_email(user)
        logger.info(f"Successfully sent OTP to {user.email}")
    except User.DoesNotExist:
        logger.error(f"User with id {user_id} does not exist.")
    except Exception as exc:
        logger.error(f"Failed to send OTP to user with id {user_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(name="compute_candidate_result_task")
def compute_candidate_result_task(candidate_result_id):
    """
    Celery task to calculate and save the auto score for a candidate's exam submission.
    """
    from vmlc.utils.functions import compute_candidate_result

    compute_candidate_result(candidate_result_id)


@shared_task(name="generate_leaderboard_snapshot_task")
def generate_leaderboard_snapshot_task(staff_id=None):
    """
    Celery task to generate and publish the leaderboard snapshot.
    """
    from vmlc.utils.functions import generate_leaderboard_snapshot

    return generate_leaderboard_snapshot(staff_id)


@shared_task(name="generate_results_snapshot_task")
def generate_results_snapshot_task(staff_id=None):
    """
    Celery task to generate and publish the results snapshot.
    """
    from vmlc.utils.functions import generate_results_snapshot

    generate_results_snapshot(staff_id)


@shared_task(name="validate_user_verification_files_task")
def validate_user_verification_files_task(user_verification_id):
    """
    Celery task to validate user verification files.
    """
    from vmlc.utils.functions import validate_user_verification_files

    validate_user_verification_files(user_verification_id)


@shared_task(name="update_staff_dashboard_cache_task")
def update_staff_dashboard_cache_task(staff_id=None):
    """
    Celery task to update the staff dashboard cache.
    """
    from vmlc.utils.functions import update_staff_dashboard_cache

    update_staff_dashboard_cache(staff_id)


@shared_task(name="update_candidate_ranking_cache_task")
def update_candidate_ranking_cache_task():
    """
    Celery task to update the candidate ranking cache for all league candidates.
    """
    from vmlc.utils.functions import update_candidate_ranking_cache

    update_candidate_ranking_cache()

@shared_task(
    name="disable_expired_feature_flags_task",
    bind=True,
    max_retries=3,
    default_retry_delay=300  # 5 minutes
)
def disable_expired_feature_flags_task(self, feature_flag_id):
    """
    Automatically disable feature flags that have reached their auto_off_date.
    
    Args:
        feature_flag_id: Primary key of the FeatureFlag to check and disable
        
    Returns:
        dict: Status of the operation with relevant details
    """
    from .models import FeatureFlag
    
    try:
        feature_flag = FeatureFlag.objects.get(pk=feature_flag_id)
    except FeatureFlag.DoesNotExist:
        logger.error(f"FeatureFlag with id {feature_flag_id} does not exist")
        return {
            "status": "error",
            "message": f"FeatureFlag {feature_flag_id} not found"
        }
    
    try:
        # Check if flag should be disabled
        if not feature_flag.auto_off_date:
            logger.info(
                f"FeatureFlag '{feature_flag.key}' (id: {feature_flag_id}) "
                "has no auto_off_date set - skipping"
            )
            return
        
        # Check if the flag is already disabled
        if not feature_flag.value:
            logger.info(
                f"FeatureFlag '{feature_flag.key}' (id: {feature_flag_id}) "
                "is already disabled"
            )
            return
        
        # Check if expiration time has been reached
        now = timezone.now()
        if feature_flag.auto_off_date > now:
            time_remaining = feature_flag.auto_off_date - now
            logger.info(
                f"FeatureFlag '{feature_flag.key}' (id: {feature_flag_id}) "
                f"not yet expired. Time remaining: {time_remaining}"
            )
            return

        feature_flag.value = False
        feature_flag.save(update_fields=["value"])
        cache.delete("registration_status")

        readable_flag_key = feature_flag.key.replace('_', ' ').title()
        
        logger.info(
            f"Successfully auto-disabled feature flag '{feature_flag.key}' "
            f"(id: {feature_flag_id}) at {now.isoformat()}"
        )
        
        # Send notification email to admins
        admin_emails = [email for _, email in settings.ADMINS]
        if admin_emails:
            send_mail_task.delay(
                subject=f"{readable_flag_key} Auto-Disabled - System Notification",
                message=(
                    f"This is an automated system notification.\n\n"
                    f"Feature Flag: {readable_flag_key}\n"
                    f"Status: Successfully disabled\n"
                    f"Scheduled Disable Time: {feature_flag.auto_off_date.strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
                    f"Actual Disable Time: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}\n\n"
                    f"This feature flag was automatically disabled as scheduled.\n\n"
                    f"Regards,\n"
                    f"VMLC System\n"
                ),
                recipient_list=admin_emails,
            )
            logger.info(
                f"Auto-disable notification sent for '{feature_flag.key}' "
                f"to {len(admin_emails)} admin(s)"
            )
        
        return
        
    except Exception as exc:
        logger.exception(
            f"Error disabling feature flag '{feature_flag.key}' "
            f"(id: {feature_flag_id}): {exc}"
        )
        
        # Retry the task if it's a transient error
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            logger.error(
                f"Max retries exceeded for disabling feature flag "
                f"'{feature_flag.key}' (id: {feature_flag_id})"
            )
            return

@shared_task(name="clear_pre_reg_user")
def clear_pre_reg_user(user_email, user_type="candidate"):

    from identity.models import PreRegUser
    from vmlc.utils.events import log_event
    try:
        pre_reg_user = PreRegUser.objects.get(email=user_email)
        pre_reg_user.delete()
        log_event(
            event_name="PRE_REG_CONVERSION",
            metadata={
                "email": user_email,
                "user_type": user_type,
                "interest_type": pre_reg_user.interest_type
            }
        )
        logger.info(f"[{user_email}] fully registered. PreRegUser entity cleared and conversion event logged.")
    except PreRegUser.DoesNotExist:
        logger.info(f"PreRegUser entity not found for [{user_email}]")



@shared_task(name="revoke_user_invite_task")
def revoke_user_invite_task(user_id):
    """
    Celery task to revoke user credentials if they haven't logged in within a week since invite.
    """
    from identity.models import User

    try:
        user = User.objects.get(pk=user_id)
        if user.last_login is None:
            user.delete()
            send_mail_task.delay(
                subject="Your account has been revoked",
                message=f"Your account has been revoked because you didn't log in within seven days of receiving your invite. "
                f"Please contact {settings.SUPPORT_EMAIL} if you have any inquires.\n\n"
                "Regards,\n\nManagement, Verboheit MLC",
                recipient_list=[user.email],
            )
            logger.info(f"Revoked credentials for user {user.email} due to inactivity.")
        else:
            logger.info(f"User {user.email} has logged in. No action taken.")
    except User.DoesNotExist:
        logger.warning(f"User with id {user_id} not found for invite revocation.")

@shared_task(bind=True, name="send_system_email_task", max_retries=20)
def send_system_email_task(
    self,
    obj_id=None,
    generated_password=None,
    is_pre_reg=False,
    is_full_reg=False,
    is_support_inquiry=False,
    is_support_notification=False
):
    """
    Send system emails for user registration and support inquiries.
    
    Args:
        obj_id: Primary key of the object (User, PreRegUser, or SupportInquiry)
        generated_password: Auto-generated password for full registration
        is_pre_reg: Flag for pre-registration email
        is_full_reg: Flag for full registration email
        is_support_inquiry: Flag for support inquiry confirmation
        is_support_notification: Flag for internal support notification
    """
    from vmlc.utils.email import (
        send_system_email,
        build_registration_welcome_email,
        build_pre_registration_email,
        build_support_confirmation_email,
        build_support_notification_email,
    )
    from identity.models import User, PreRegUser
    from vmlc.models import SupportInquiry

    if not obj_id:
        logger.error("No object ID provided for email task")
        return

    try:
        # Determine object type and build email content
        if is_pre_reg:
            user = PreRegUser.objects.get(pk=obj_id)
            subject, message = build_pre_registration_email(user=user)
            recipient_email = user.email
            email_type = "pre-registration"
            
        elif is_full_reg:
            user = User.objects.get(pk=obj_id)
            subject, message = build_registration_welcome_email(
                user=user,
                generated_password=generated_password
            )
            recipient_email = user.email
            email_type = "full registration"
            
        elif is_support_inquiry:
            inquiry = SupportInquiry.objects.get(pk=obj_id)
            subject, message = build_support_confirmation_email(inquiry=inquiry)
            recipient_email = inquiry.email
            email_type = "support inquiry"
            
        elif is_support_notification:
            inquiry = SupportInquiry.objects.get(pk=obj_id)
            subject, message = build_support_notification_email(inquiry=inquiry)
            recipient_email = settings.SUPPORT_EMAIL
            email_type = "support notification"
            
        else:
            logger.error(f"No valid email type specified for object ID {obj_id}")
            return

    except (User.DoesNotExist, PreRegUser.DoesNotExist, SupportInquiry.DoesNotExist) as e:
        logger.error(f"Object not found for email task: {e}")
        return
    
    # Send email with retry logic
    try:
        send_system_email(subject, message, recipient_email)
        logger.info(f"{email_type.capitalize()} email sent successfully to {recipient_email}")
        
    except Exception as e:
        logger.error(
            f"Failed to send {email_type} email to {recipient_email} "
            f"(attempt {self.request.retries + 1}/{self.max_retries}): {e}"
        )
        
        if self.request.retries >= self.max_retries - 1:
            logger.error(
                f"Max retries reached for {email_type} email to {recipient_email}. "
                f"Object ID: {obj_id}"
            )
            return
        
        raise self.retry(exc=e, countdown=60)

@shared_task(bind=True, name="send_welcome_mail_task", max_retries=20)
def send_welcome_mail_task(self, user_id=None, generated_password=None, is_pre_reg=False):
    """Send welcome email to newly registered user."""
    from .utils.auth import send_welcome_email
    from identity.models import User, PreRegUser

    if is_pre_reg:
        user = PreRegUser.objects.get(pk=user_id)
    else:
        user = User.objects.get(pk=user_id) 

    try:
        send_welcome_email(user, generated_password)
        logger.info(f"Welcome email sent to {user.email}")
    except Retry:
        raise
    except Exception as e:
        logger.error(f"Failed to send welcome email to {user.email}: {e}")
        if self.request.retries >= 3:
            logger.error(f"Max retries reached for user {user_id}. Giving up.")
            return

        raise self.retry(exc=e, countdown=60)


@shared_task(name="generate_stats_overview_task")
def generate_stats_overview_task():
    """
    Asynchronously generates and caches the statistics overview.
    """
    from vmlc.v2.utils import CacheKeys
    data = generate_stats_overview_data()
    cache.set(CacheKeys.STATS_OVERVIEW, data, timeout=3600)  # Cache for 1 hour
    logger.info("Successfully generated and cached stats overview.")


@shared_task(
    bind=True,
    name="upload_user_documents_task",
    max_retries=5,
    default_retry_delay=60,
    queue="files",
    acks_late=True,
    reject_on_worker_lost=True,
)
def upload_user_documents_task(self, user_id, file_mappings):
    """
    Asynchronously uploads multiple user documents from temporary paths.
    
    Args:
        user_id: ID of the user
        file_mappings: List of dicts with keys: temp_path, field_name, original_name
    """
    from identity.models import User, UserVerification
    
    uploaded_files = []
    failed_files = []
    
    try:
        user = User.objects.get(pk=user_id)
        verification, _ = UserVerification.objects.get_or_create(user=user)
        
        logger.info(f"Starting document upload for user {user_id} with {len(file_mappings)} files")
        
        for file_info in file_mappings:
            temp_path = file_info["temp_path"]
            field_name = file_info["field_name"]
            original_name = file_info["original_name"]
            
            try:
                # Check if file exists, with retry logic for sync delays
                if not os.path.exists(temp_path):
                    if self.request.retries < 3:
                        logger.warning(
                            f"Temp file {temp_path} not found (attempt {self.request.retries + 1}). "
                            f"Will retry..."
                        )
                        # Cleanup any successfully uploaded files before retry
                        _cleanup_temp_files(uploaded_files)
                        raise self.retry(countdown=5)
                    else:
                        logger.error(f"Temp file {temp_path} not found after retries")
                        failed_files.append({"file": temp_path, "error": "File not found"})
                        continue
                
                # Verify file is readable and has content
                file_size = os.path.getsize(temp_path)
                if file_size == 0:
                    logger.error(f"Temp file {temp_path} is empty")
                    failed_files.append({"file": temp_path, "error": "Empty file"})
                    os.remove(temp_path)
                    continue
                
                logger.info(f"Uploading {field_name} ({file_size} bytes) for user {user_id}")
                
                # Upload to storage
                with open(temp_path, "rb") as f:
                    django_file = File(f, name=original_name)
                    
                    if field_name == "face_id":
                        verification.face_id.save(original_name, django_file, save=True)
                    elif field_name == "id_card":
                        verification.id_card.save(original_name, django_file, save=True)
                    elif field_name == "verification_document":
                        verification.verification_document.save(original_name, django_file, save=True)
                    else:
                        logger.error(f"Unknown field_name: {field_name}")
                        failed_files.append({"file": temp_path, "error": f"Unknown field: {field_name}"})
                        os.remove(temp_path)
                        continue
                
                uploaded_files.append(temp_path)
                logger.info(f"Successfully uploaded {field_name} for user {user.email}")
                
            except IOError as e:
                logger.error(f"IOError processing {temp_path}: {e}")
                if self.request.retries < self.max_retries:
                    _cleanup_temp_files(uploaded_files)
                    raise self.retry(exc=e, countdown=10)
                failed_files.append({"file": temp_path, "error": str(e)})
            except Exception as e:
                logger.error(f"Unexpected error processing {temp_path}: {e}")
                failed_files.append({"file": temp_path, "error": str(e)})
        
        # Cleanup temp files
        _cleanup_temp_files(uploaded_files + [f["file"] for f in failed_files])
        
        if failed_files:
            logger.error(f"Failed to upload some files for user {user_id}: {failed_files}")
            # Optionally send notification to admins
        
        if not uploaded_files and failed_files:
            # All uploads failed
            raise Exception(f"All file uploads failed for user {user_id}")
        
        logger.info(
            f"Document upload task completed for user {user_id}. "
            f"Success: {len(uploaded_files)}, Failed: {len(failed_files)}"
        )
        
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found during document upload")
        _cleanup_temp_files([f["temp_path"] for f in file_mappings])
    except Retry:
        raise
    except Exception as exc:
        logger.error(f"Failed to upload documents for user {user_id}: {exc}", exc_info=True)
        _cleanup_temp_files([f["temp_path"] for f in file_mappings])
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60)
        else:
            # Final failure - log and potentially alert admins
            logger.critical(
                f"Permanent failure uploading documents for user {user_id} "
                f"after {self.max_retries} retries"
            )


def _cleanup_temp_files(file_paths):
    """Helper to cleanup temporary files."""
    for path in file_paths:
        try:
            if os.path.exists(path):
                os.remove(path)
                logger.debug(f"Cleaned up temp file: {path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp file {path}: {e}")