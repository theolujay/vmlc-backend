import logging

from vmlc.models import Event

logger = logging.getLogger(__name__)


def log_event(event_name, actor=None, metadata=None):
    """
    Logs a platform event safely (fire-and-forget).

    Args:
        event_name (str): Name of the event.
        actor (User, optional): User who triggered the event.
        metadata (dict, optional): Additional context.
    """
    if metadata is None:
        metadata = {}

    try:
        Event.objects.create(event_name=event_name, actor=actor, metadata=metadata)
    except Exception as e:
        # Fire-and-forget: we don't want to break the user flow if logging fails
        # But we do want to know about it in the logs
        logger.error(f"Failed to log event '{event_name}': {str(e)}", exc_info=True)
