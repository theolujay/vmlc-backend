import os
import logging

from django.conf import settings
from django.core.files import File
from django.core.cache import cache
from django.core.mail import send_mail
from celery import shared_task
from celery.exceptions import Retry

from vmlc.models import PreRegUser
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
    from .models import User
    from .utils.auth import send_otp_to_email

    try:
        user = User.objects.get(pk=user_id)
        send_otp_to_email(user)
        logger.info(f"Successfully sent OTP to {user.email}")
    except User.DoesNotExist:
        logger.error(f"User with id {user_id} does not exist.")
    except Exception as exc:
        logger.error(f"Failed to send OTP to user with id {user_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(name="calculate_and_save_auto_score_task")
def calculate_and_save_auto_score_task(candidate_score_id):
    """
    Celery task to calculate and save the auto score for a candidate's exam submission.
    """
    from vmlc.utils.functions import calculate_and_save_auto_score

    calculate_and_save_auto_score(candidate_score_id)


@shared_task(name="generate_leaderboard_snapshot_task")
def generate_leaderboard_snapshot_task(staff_id=None):
    """
    Celery task to generate and publish the leaderboard snapshot.
    """
    from vmlc.utils.functions import generate_leaderboard_snapshot

    return generate_leaderboard_snapshot(staff_id)


@shared_task(name="generate_scores_snapshot_task")
def generate_scores_snapshot_task(staff_id=None):
    """
    Celery task to generate and publish the scores snapshot.
    """
    from vmlc.utils.functions import generate_scores_snapshot

    generate_scores_snapshot(staff_id)


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
    If a staff_id is provided, it updates the cache for that specific staff member.
    Otherwise, it updates the cache for all staff members.
    """
    from vmlc.utils.functions import update_staff_dashboard_cache

    update_staff_dashboard_cache(staff_id)


@shared_task(name="update_candidate_dashboard_cache_task")
def update_candidate_dashboard_cache_task(candidate_id=None):
    """
    Celery task to update the candidate dashboard cache.
    """
    from vmlc.utils.functions import update_candidate_dashboard_cache

    update_candidate_dashboard_cache(candidate_id)


@shared_task(name="update_candidate_ranking_cache_task")
def update_candidate_ranking_cache_task():
    """
    Celery task to update the candidate ranking cache for all league candidates.
    """
    from vmlc.utils.functions import update_candidate_ranking_cache

    update_candidate_ranking_cache()


@shared_task(name="revoke_user_invite_task")
def revoke_user_invite_task(user_id):
    """
    Celery task to revoke user credentials if they haven't logged in within a week since invite.
    """
    from .models import User

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


@shared_task(bind=True, name="send_welcome_mail_task", max_retries=20)
def send_welcome_mail_task(self, user_id=None, generated_password=None, is_pre_reg=False):
    """Send welcome email to newly registered user."""
    from .utils.auth import send_welcome_email
    from .models import User

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
    data = generate_stats_overview_data()
    cache.set("stats_overview", data, timeout=3600)  # Cache for 1 hour
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
    from .models import User, UserVerification
    
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