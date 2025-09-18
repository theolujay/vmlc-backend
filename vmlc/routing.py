from django.urls import path

from .consumers import LeaderboardConsumer

websocket_urlpatterns = [
    path("ws/leaderboard/", LeaderboardConsumer.as_asgi()),
]
