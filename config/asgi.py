"""
ASGI config for core project.

It exposes the ASGI callable as a module-level variable named ``application``.
"""

import os

import django
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")
django.setup()

# It's important to get the django_asgi_app before importing any other
# Django components, especially middleware, to ensure all apps are loaded.
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter

import comms.routing
from comms.middleware import DualAuthMiddlewareStack

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": DualAuthMiddlewareStack(
            URLRouter(comms.routing.websocket_urlpatterns)
        ),
    }
)
