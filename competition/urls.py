from django.urls import path
from competition.views import PublishStandingsView

app_name = "competition"

urlpatterns = [
    path("standings/publish/", PublishStandingsView.as_view(), name="publish-standings"),
]
