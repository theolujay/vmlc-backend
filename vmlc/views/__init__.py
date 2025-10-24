"""
This package contains all the views for the API.
"""

from .answer import SubmitAnswersView
from .auth import (
    RefreshTokenView,
    VerifyEmailOTPView,
    ResendEmailOTPView,
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
    AccountManagementView,
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
    ToggleLeaderboardVisibilityView,
)
from .question import (
    QuestionListView,
    QuestionDetailView,
    QuestionExamAssociationView,
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
from .user import (
    UserVerificationStatusView,
    UserVerificationUploadView,
    UserVerificationDocumentView,
    UserVerificationListView,
    UserVerificationActionView,
    StaffInviteView,
)
from .health import health_check

__all__ = [
    # answer
    "SubmitAnswersView",
    # auth
    "RefreshTokenView",
    "VerifyEmailOTPView",
    "ResendEmailOTPView",
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
    "ToggleLeaderboardVisibilityView",
    # question
    "QuestionListView",
    "QuestionDetailView",
    "QuestionExamAssociationView",
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
    # user
    "UserVerificationStatusView",
    "UserVerificationUploadView",
    "UserVerificationDocumentView",
    "UserVerificationListView",
    "UserVerificationActionView",
    "StaffInviteView",
]
