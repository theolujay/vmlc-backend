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
    AssignCandidateRoleView,
    CandidateMeView,
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
from .metrics import RegistrationMetricsView
from .question import (
    QuestionListView,
    QuestionDetailView,
    QuestionExamAssociationView,
    BulkAddQuestionsToExamsView,
    BulkQuestionArchiveView,
)
from .exam_result import (
    SubmitScoreView,
    PublishScoresView,
)
from .staff import (
    StaffListView,
    AssignStaffRoleView,
    StaffMeView,
)
from .status import (
    health_check,
    stats_overview,
    registration_status,
)
from .user import (
    AccountManagementView,
    UserVerificationStatusView,
    UserVerificationUploadView,
    UserVerificationDocumentView,
    UserVerificationListView,
    UserVerificationActionView,
    CandidateInviteView,
    StaffInviteView,
    UserListView,
    UserDetailView,
)

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
    "AssignCandidateRoleView",
    # dashboard
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
    # status
    "health_check",
    "stats_overview",
    "registration_status",
    # result
    # "CandidateExamResultListView",
    "SubmitScoreView",
    "PublishScoresView",
    # staff
    "StaffMeView",
    "StaffListView",
    "AssignStaffRoleView",
    # user
    "UserVerificationStatusView",
    "UserVerificationUploadView",
    "UserVerificationDocumentView",
    "UserVerificationListView",
    "UserVerificationActionView",
    "StaffInviteView",
    "CandidateInviteView",
    "UserListView",
    "UserDetailView",
    "RegistrationMetricsView",
]
