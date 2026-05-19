import logging
import os

from celery import shared_task
from celery.exceptions import Retry
from django.conf import settings
from django.core.files import File

logger = logging.getLogger(__name__)


@shared_task(name="clear_pre_reg_user")
def clear_pre_reg_user(user_email, user_type="candidate"):
    from core.utils.events import log_event
    from identity.models import PreRegUser

    try:
        pre_reg_user = PreRegUser.objects.get(email=user_email)
        pre_reg_user.delete()
        log_event(
            event_name="PRE_REG_CONVERSION",
            metadata={
                "email": user_email,
                "user_type": user_type,
                "interest_type": pre_reg_user.interest_type,
            },
        )
        logger.info(
            f"[{user_email}] fully registered. PreRegUser entity cleared and conversion event logged."
        )
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
            from comms.tasks import send_mail_task

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
    from identity.models import User, UserVerification

    uploaded_files = []
    failed_files = []

    try:
        user = User.objects.get(pk=user_id)
        verification, _ = UserVerification.objects.get_or_create(user=user)

        logger.info(
            f"Starting document upload for user {user_id} with {len(file_mappings)} files"
        )

        for file_info in file_mappings:
            temp_path = file_info["temp_path"]
            field_name = file_info["field_name"]
            original_name = file_info["original_name"]

            try:
                if not os.path.exists(temp_path):
                    if self.request.retries < 3:
                        logger.warning(
                            f"Temp file {temp_path} not found (attempt {self.request.retries + 1}). "
                            f"Will retry..."
                        )
                        _cleanup_temp_files(uploaded_files)
                        raise self.retry(countdown=5)
                    else:
                        logger.error(f"Temp file {temp_path} not found after retries")
                        failed_files.append(
                            {"file": temp_path, "error": "File not found"}
                        )
                        continue

                file_size = os.path.getsize(temp_path)
                if file_size == 0:
                    logger.error(f"Temp file {temp_path} is empty")
                    failed_files.append({"file": temp_path, "error": "Empty file"})
                    os.remove(temp_path)
                    continue

                logger.info(
                    f"Uploading {field_name} ({file_size} bytes) for user {user_id}"
                )

                with open(temp_path, "rb") as f:
                    django_file = File(f, name=original_name)

                    if field_name == "face_id":
                        verification.face_id.save(original_name, django_file, save=True)
                    elif field_name == "id_card":
                        verification.id_card.save(original_name, django_file, save=True)
                    elif field_name == "verification_document":
                        verification.verification_document.save(
                            original_name, django_file, save=True
                        )
                    else:
                        logger.error(f"Unknown field_name: {field_name}")
                        failed_files.append(
                            {"file": temp_path, "error": f"Unknown field: {field_name}"}
                        )
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

        _cleanup_temp_files(uploaded_files + [f["file"] for f in failed_files])

        if failed_files:
            logger.error(
                f"Failed to upload some files for user {user_id}: {failed_files}"
            )

        if not uploaded_files and failed_files:
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
        logger.error(
            f"Failed to upload documents for user {user_id}: {exc}", exc_info=True
        )
        _cleanup_temp_files([f["temp_path"] for f in file_mappings])
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60)
        else:
            logger.critical(
                f"Permanent failure uploading documents for user {user_id} "
                f"after {self.max_retries} retries"
            )


def _cleanup_temp_files(file_paths):
    for path in file_paths:
        try:
            if os.path.exists(path):
                os.remove(path)
                logger.debug(f"Cleaned up temp file: {path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp file {path}: {e}")
