"""
ASGI config for core project.

It exposes the ASGI callable as a module-level variable named ``application``.
"""

import os
import django
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")
django.setup()

from channels.routing import ProtocolTypeRouter, URLRouter

from comms.middleware import DualAuthMiddlewareStack
import comms.routing

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": DualAuthMiddlewareStack(
            URLRouter(comms.routing.websocket_urlpatterns)
        ),
    }
)
