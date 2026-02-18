from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path("v1/ws/notifications/", consumers.NotificationConsumer.as_asgi()),
    path("v1/ws/support/thread/<uuid:thread_id>/", consumers.SupportChatConsumer.as_asgi()),
]
