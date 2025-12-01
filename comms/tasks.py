import logging

from django.db import DatabaseError
from celery import shared_task

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
    from comms.utils import send_broadcast

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
