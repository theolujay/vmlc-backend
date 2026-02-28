from django.urls import path, re_path
from . import consumers

websocket_urlpatterns = [
    path("v1/ws/", consumers.UnifiedConsumer.as_asgi()),
    path("v1/ws/notifications/", consumers.UnifiedConsumer.as_asgi()),
    path("v1/ws/helpdesk/thread/", consumers.UnifiedConsumer.as_asgi()),
]
