from django.urls import path
from .import consumers

websocket_urlpatterns = [
    path("v1/ws/notifications/", consumers.NotificationConsumer.as_asgi())
]