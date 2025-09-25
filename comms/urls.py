from django.urls import path

from .views import (
    BroadcastView
)

app_name = "comms"

urlpatterns = [
    path('broadcasts/', BroadcastView.as_view(), name='broadcast-list-create'),
    path('broadcasts/<int:broadcast_id>/', BroadcastView.as_view(), name='broadcast-detail'),
]
