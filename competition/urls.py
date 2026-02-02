from django.urls import path
from competition.views import (
    PublishStandingsView, 
    RetrieveStandingsView, 
    LeagueLeaderboardView,
    StaffCompetitionDashboardView,
    RetrieveCandidateStandingView,
    LeagueCandidateLeaderboardView,
    CandidateDashboardView,
    PromoteCandidatesView,
)

app_name = "competition"

urlpatterns = [
    path("dashboard/staff", StaffCompetitionDashboardView.as_view(), name="competition-dashboard"),
    path("dashboard/candidate/", CandidateDashboardView.as_view(), name="candidate-dashboard"),
    path("standings/publish/", PublishStandingsView.as_view(), name="publish-standings"),
    path("standings/<uuid:exam_id>/", RetrieveStandingsView.as_view(), name="retrieve-standings"),
    path("standings/<uuid:exam_id>/candidate/<uuid:candidate_id>/", RetrieveCandidateStandingView.as_view(), name="candidate-standing-detail"),
    path("leaderboard/league/", LeagueLeaderboardView.as_view(), name="league-leaderboard"),
    path("leaderboard/league/candidate/<uuid:candidate_id>/", LeagueCandidateLeaderboardView.as_view(), name="league-candidate-cumulative-detail"),
    path("promote/", PromoteCandidatesView.as_view(), name="promote-candidates"),
]
