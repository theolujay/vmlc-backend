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