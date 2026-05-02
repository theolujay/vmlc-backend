"""
This package contains all the serializers for the API.
"""

from .answer import (
    CandidateAnswerSerializer,
    CandidateAnswerBulkSerializer,
)
from .auth import (
    VerifyEmailOTPSerializer,
    SendEmailOTPSerializer,
    RequestPasswordChangeSerializer,
    PasswordChangeOTPConfirmSerializer,
    PasswordChangeSerializer,
)
from .candidate import (
    MinimalCandidateSerializer,
    CandidateListSerializer,
    CandidateDetailSerializer,
)
from .comms import BulkNotificationSerializer
from .exam import (
    ExamListSerializer,
    ExamDetailSerializer,
    CandidateExamSerializer,
    ExamResultSerializer,
)
from .leaderboard import (
    PublishLeaderboardSerializer,
    CandidateLeaderboardPerfSerializer,
    LeaderboardSnapshotListSerializer,
)
from .question import (
    QuestionListSerializer,
    QuestionDetailSerializer,
    CandidateQuestionSerializer,
)
from .registration import (
    CandidateRegistrationSerializer,
    StaffRegistrationSerializer,
    CandidateInviteSerializer,
    StaffInviteSerializer,
)
from ..v2.serializers.registration import RegistrationV2Serializer
from .role import (
    CandidateRoleSerializer,
    StaffRoleSerializer,
)
from .exam_result import (
    CandidateExamResultSerializer,
    SubmitScoreSerializer,
    CandidateExamScoreSerializer,
)
from .staff import (
    MinimalStaffSerializer,
    StaffListSerializer,
    StaffDetailSerializer,
)
from .user import (
    UserSerializer,
    MinimalUserSerializer,
    UserVerificationStatusSerializer,
    UserVerificationUploadSerializer,
    UserVerificationActionSerializer,
    UserVerificationListSerializer,
)
from .user_profile import UserProfileDetailSerializer, UserProfileListSerializer


__all__ = [
    # answer
    "CandidateAnswerSerializer",
    "CandidateAnswerBulkSerializer",
    # auth
    "VerifyEmailOTPSerializer",
    "SendEmailOTPSerializer",
    "RequestPasswordChangeSerializer",
    "PasswordChangeOTPConfirmSerializer",
    "PasswordChangeSerializer",
    # candidate
    "MinimalCandidateSerializer",
    "CandidateListSerializer",
    "CandidateDetailSerializer",
    # comms
    "BulkNotificationSerializer",
    # exam
    "ExamListSerializer",
    "ExamDetailSerializer",
    "CandidateExamSerializer",
    "ExamResultSerializer",
    # leaderboard
    "LeaderboardSnapshotListSerializer",
    "CandidateLeaderboardPerfSerializer",
    "PublishLeaderboardSerializer",
    # question
    "QuestionListSerializer",
    "QuestionDetailSerializer",
    "CandidateQuestionSerializer",
    # registration
    "CandidateRegistrationSerializer",
    "StaffRegistrationSerializer",
    "CandidateInviteSerializer",
    "StaffInviteSerializer",
    "RegistrationV2Serializer",
    # role
    "CandidateRoleSerializer",
    "StaffRoleSerializer",
    # result
    "CandidateExamResultSerializer",
    "SubmitScoreSerializer",
    "CandidateExamScoreSerializer",
    # staff
    "MinimalStaffSerializer",
    "StaffListSerializer",
    "StaffDetailSerializer",
    "StaffInviteSerializer",
    # user
    "UserSerializer",
    "MinimalUserSerializer",
    "UserVerificationStatusSerializer",
    "UserVerificationUploadSerializer",
    "UserVerificationActionSerializer",
    "UserVerificationListSerializer",
    "UserProfileDetailSerializer",
    "UserProfileListSerializer",
]
