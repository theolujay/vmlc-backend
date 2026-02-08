from django.urls import path
from competition.views import (
    PublishRankingSnapshotView,
    RetrieveRankingSnapshotView,
    LeagueLeaderboardView,
    StaffCompetitionDashboardView,
    RetrieveCandidateRankingSnapshotEntryView,
    LeagueCandidateLeaderboardView,
    CandidateDashboardView,
    PromoteCandidatesView,
)

app_name = "competition"

urlpatterns = [
    path(
        "dashboard/staff",
        StaffCompetitionDashboardView.as_view(),
        name="staff-competition-dashboard",
    ),
    path(
        "dashboard/candidate/",
        CandidateDashboardView.as_view(),
        name="candidate-dashboard",
    ),
    path(
        "rankings/publish/",
        PublishRankingSnapshotView.as_view(),
        name="publish-ranking-snapshot",
    ),
    path(
        "rankings/<uuid:exam_id>/",
        RetrieveRankingSnapshotView.as_view(),
        name="retrieve-ranking-snapshot",
    ),
    path(
        "rankings/<uuid:exam_id>/candidate/<uuid:candidate_id>/",
        RetrieveCandidateRankingSnapshotEntryView.as_view(),
        name="candidate-ranking-snapshot-detail",
    ),
    path(
        "leaderboard/league/",
        LeagueLeaderboardView.as_view(),
        name="league-leaderboard",
    ),
    path(
        "leaderboard/league/candidate/<uuid:candidate_id>/",
        LeagueCandidateLeaderboardView.as_view(),
        name="league-candidate-cumulative-detail",
    ),
    path(
        "promote-candidates/",
        PromoteCandidatesView.as_view(),
        name="promote-candidates",
    ),
]
