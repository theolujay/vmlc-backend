from django.urls import path
from competition.views import PublishStandingsView, RetrieveStandingsView

app_name = "competition"

urlpatterns = [
    path("standings/publish/", PublishStandingsView.as_view(), name="publish-standings"),
    path("standings/<int:pk>/", RetrieveStandingsView.as_view(), name="retrieve-standings"),
]
