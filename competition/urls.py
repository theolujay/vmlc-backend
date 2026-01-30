from django.urls import path
from competition.views import PublishStandingsView, RetrieveStandingsView, LeagueLeaderboardView

app_name = "competition"

urlpatterns = [
    path("standings/publish/", PublishStandingsView.as_view(), name="publish-standings"),
    path("standings/<int:pk>/", RetrieveStandingsView.as_view(), name="retrieve-standings"),
    path("leaderboard/league/", LeagueLeaderboardView.as_view(), name="league-leaderboard"),
]
