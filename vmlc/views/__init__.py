"""
This package contains all the views for the API.
"""

from .answer import SubmitAnswersView
from .auth import (
    RefreshTokenView,
    VerifyEmailOTPView,
    SendEmailOTPView,
    RequestPasswordChangeView,
    PasswordChangeOTPConfirmView,
    PasswordChangeView,
    ResendPasswordChangeOTPView,
    CustomTokenObtainPairSerializer,
    LoginView,
    LogoutView,
)
from .candidate import (
    CandidateListView,
    CandidateDetailView,
    AssignCandidateRoleView,
    CandidateMeView,
)
from .dashboard import (
    CandidateDashboardView,
    StaffDashboardView,
)
from .exam import (
    ExamListView,
    ExamDetailView,
    ExamResultsView,
    ExamQuestionsView,
    ExamHistoryView,
    candidate_take_exam,
)
from .leaderboard import (
    PublishLeaderboardView,
    LoadLeaderboardView,
    LoadLeaderboardDetailView,
)
from .question import (
    QuestionListView,
    QuestionDetailView,
    QuestionExamAssociationView,
    BulkAddQuestionsToExamsView,
    BulkQuestionArchiveView,
)
from .registration import (
    CandidateRegistrationView,
    StaffRegistrationView,
    ToggleCandidateRegistrationView,
    ToggleStaffRegistrationView,
)
from .root import root
from .score import (
    # CandidateScoreListView,
    SubmitScoreView,
    PublishScoresView,
)
from .staff import (
    StaffListView,
    StaffDetailView,
    AssignStaffRoleView,
    StaffMeView,
)
from .stats import stats_overview
from .user import (
    AccountManagementView,
    UserVerificationStatusView,
    UserVerificationUploadView,
    UserVerificationDocumentView,
    UserVerificationListView,
    UserVerificationActionView,
    CandidateInviteView,
    StaffInviteView,
)
from .health import health_check

__all__ = [
    # answer
    "SubmitAnswersView",
    # auth
    "RefreshTokenView",
    "VerifyEmailOTPView",
    "SendEmailOTPView",
    "RequestPasswordChangeView",
    "PasswordChangeOTPConfirmView",
    "PasswordChangeView",
    "ResendPasswordChangeOTPView",
    "CustomTokenObtainPairSerializer",
    "LoginView",
    "LogoutView",
    # candidate
    "CandidateMeView",
    "CandidateListView",
    "CandidateDetailView",
    "AssignCandidateRoleView",
    # dashboard
    "CandidateDashboardView",
    "StaffDashboardView",
    "AccountManagementView",
    # exam
    "ExamListView",
    "ExamDetailView",
    "ExamResultsView",
    "ExamQuestionsView",
    "ExamHistoryView",
    "candidate_take_exam",
    # leaderboard
    "PublishLeaderboardView",
    "LoadLeaderboardView",
    "LoadLeaderboardDetailView",
    # question
    "QuestionListView",
    "QuestionDetailView",
    "QuestionExamAssociationView",
    "BulkAddQuestionsToExamsView",
    "BulkQuestionArchiveView",
    # registration
    "CandidateRegistrationView",
    "StaffRegistrationView",
    "ToggleCandidateRegistrationView",
    "ToggleStaffRegistrationView",
    # root
    "root",
    # health
    "health_check",
    # score
    # "CandidateScoreListView",
    "SubmitScoreView",
    "PublishScoresView",
    # staff
    "StaffMeView",
    "StaffListView",
    "StaffDetailView",
    "AssignStaffRoleView",
    # stats
    "stats_overview",
    # user
    "UserVerificationStatusView",
    "UserVerificationUploadView",
    "UserVerificationDocumentView",
    "UserVerificationListView",
    "UserVerificationActionView",
    "StaffInviteView",
    "CandidateInviteView",
]
