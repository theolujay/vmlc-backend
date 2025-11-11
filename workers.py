from typing import Any, Dict
from uvicorn.workers import UvicornWorker as BaseUvicornWorker


class UvicornWorker(BaseUvicornWorker):
    """
    Custom Uvicorn worker that disables lifespan protocol.

    This prevents the 'ASGI lifespan protocol appears unsupported' warning
    when using Django Channels with Gunicorn.
    """

    CONFIG_KWARGS: Dict[str, Any] = {"loop": "auto", "http": "auto", "lifespan": "off"}
