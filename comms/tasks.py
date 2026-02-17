from datetime import timedelta
import logging
from typing import List

from django.db import DatabaseError
from celery import shared_task

from identity.models import User
from vmlc.utils.exceptions import (
    ServerError,
)

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="send_broadcast_task",
    max_retries=3,
    default_retry_delay=60,
    queue="comms",
)
def send_broadcast_task(self, broadcast_id):
    """
    Send a broadcast to multiple recipients across different mediums.
    """
    from comms.functions import send_broadcast

    try:
        result = send_broadcast(broadcast_id)
        return result

    except (DatabaseError, ServerError) as e:
        logger.warning(
            "Retryable error for broadcast %s (attempt %s/%s): %s",
            broadcast_id,
            self.request.retries + 1,
            self.max_retries,
            str(e),
        )
        raise self.retry(exc=e, countdown=60)

    except Exception as e:
        logger.exception(
            "Fatal error during broadcast %s: %s",
            broadcast_id,
            str(e),
        )
        raise


@shared_task(name="notify_prereg_users_via_whatsapp_task")
def notify_prereg_users_via_whatsapp_task():
    """
    Notify PreRegUser entities via WhatsApp if registration is open.
    """
    import re
    from django.conf import settings
    from vmlc.models import FeatureFlag
    from identity.models import PreRegUser
    from comms.utils import send_bulk_phone_msg

    if not FeatureFlag.get_bool("candidate_registration"):
        logger.info("Candidate registration is closed. Skipping WhatsApp notification.")
        return

    # Filter for candidates
    candidates = PreRegUser.objects.filter(
        interest_type=PreRegUser.InterestType.CANDIDATE
    )

    if not candidates.exists():
        logger.info("No pre-registered candidates found.")
        return

    phones = []
    for candidate in candidates:
        if not candidate.phone:
            continue

        # Clean phone number
        phone = candidate.phone.strip()
        if re.match(r"^(\+234[789][01]\d{8})$", phone):
            phones.append(phone)
        elif re.match(r"^(0[789][01]\d{8})$", phone):
            phones.append("+234" + phone[1:])

    if not phones:
        logger.info("No valid phone numbers found for pre-registered candidates.")
        return

    # Deduplicate phones
    phones = list(set(phones))

    registration_url = f"{settings.LANDING_BASE_URL}/register"
    message = (
        f"Hi! Registration for the Verboheit Mathematics League Competition is now open. "
        f"You previously expressed interest. Please complete your registration here: {registration_url}"
    )

    result = send_bulk_phone_msg(body=message, recipients=phones, medium="whatsapp")

    logger.info(
        f"Pre-reg WhatsApp notification task completed. "
        f"Success: {result['success_count']}, Failed: {result['failure_count']}"
    )

@shared_task(
    bind=True,
    name="notify_user_task",
    max_retries=3,
    default_retry_delay=60,
    queue="comms",
)
def notify_user_task(
    self,
    user: User,
    subject: str,
    message: str,
    mediums: List[str],
    type: str,
):
    from comms.functions import notify_user

    results = notify_user(
        user=user,
        subject=subject,
        message=message,
        mediums=mediums,
        type=type,
    )
    if not results["email"]:
        raise self.retry(exc="Email medium failed", countdown=60)

@shared_task(name="notify_candidates_about_exam_task")
def notify_candidates_about_exam_task(exam_id, event_type):
    """
    Unified task to notify candidates about exam events (scheduled or started).
    """
    from vmlc.models import Exam
    from comms.functions import notify_candidates_about_exam

    try:
        exam = Exam.objects.select_related("competition_slot__competition_stage").get(
            id=exam_id
        )

        notify_candidates_about_exam(exam=exam, event_type=event_type)

    except Exam.DoesNotExist:
        logger.error(f"Exam {exam_id} not found for notification task.")


@shared_task(
    bind=True,
    name="send_bulk_sms_task",
    max_retries=12,
    default_retry_delay=3600,  # 1 hour
    queue="comms",
)
def send_bulk_sms_task(self, body: str, recipients: List[str], broadcast_log_id: int = None):
    """
    Sends bulk SMS and retries if the balance is insufficient.
    Updates the BroadcastLog status if broadcast_log_id is provided.
    """
    from comms.services import kudi_sms
    from comms.utils import send_low_kudi_balance_to_slack
    from comms.models import BroadcastLog

    log = None
    if broadcast_log_id:
        try:
            log = BroadcastLog.objects.get(id=broadcast_log_id)
        except BroadcastLog.DoesNotExist:
            logger.error(f"BroadcastLog with id {broadcast_log_id} not found.")
            # Don't retry if the log doesn't exist, as it's a permanent failure.
            return

    try:
        estimated_cost = kudi_sms.estimate_cost(body, len(recipients))
        balance_resp = kudi_sms.get_balance()
        current_balance = kudi_sms.parse_balance(balance_resp.get("balance", "0"))

        logger.info(
            "Kudi SMS Task: Cost ~%s N, Balance: %s N",
            estimated_cost,
            current_balance,
        )

        if current_balance < estimated_cost:
            logger.warning(
                "Insufficient Kudi balance for bulk SMS (log: %s). Retrying in 1 hour.", broadcast_log_id
            )
            if self.request.retries == 0:
                send_low_kudi_balance_to_slack(
                    current_balance, estimated_cost, len(recipients)
                )
            raise self.retry(countdown=3600)

        kudi_recipients = ",".join([r.lstrip("+") for r in recipients])
        response = kudi_sms.send_bulk_sms(message=body, recipients=kudi_recipients)

        is_success = response.get("status") == "success" or response.get("error") == 0

        if is_success:
            logger.info("Bulk SMS via Kudi sent successfully for log %s.", broadcast_log_id)
            if log:
                log.status = BroadcastLog.MediumStatus.SENT
                log.message = f"Successfully sent to {len(recipients)} recipients."
                log.save(update_fields=["status", "message"])
            return {"status": "SUCCESS", "count": len(recipients)}
        else:
            message = response.get("message", "Unknown error from Kudi")
            logger.error("Bulk SMS via Kudi failed for log %s: %s. Retrying in 5 mins.", broadcast_log_id, message)
            if log:
                log.message = f"Kudi API Error: {message}. Retrying..."
                log.save(update_fields=["message"])
            raise self.retry(countdown=300)

    except Exception as e:
        logger.exception("Unexpected error in send_bulk_sms_task for log %s.", broadcast_log_id)
        if log:
            log.status = BroadcastLog.MediumStatus.FAILED
            log.message = f"Fatal Error: {str(e)}"
            log.save(update_fields=["status", "message"])
        # Re-raise to let Celery handle it as a task failure
        raise
