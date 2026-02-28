from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path("v1/ws/", consumers.UnifiedConsumer.as_asgi()),
]
