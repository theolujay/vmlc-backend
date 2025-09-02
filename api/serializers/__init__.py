"""
This package contains all the serializers for the API.
"""

from .answer import (
    CandidateAnswerSerializer,
    CandidateAnswerBulkSerializer,
)
from .auth import (
    VerifyEmailOTPSerializer,
    ResendEmailOTPSerializer,
    RequestPasswordChangeSerializer,
    PasswordChangeOTPConfirmSerializer,
    PasswordChangeSerializer,
)
from .candidate import (
    MinimalCandidateSerializer,
    CandidateListSerializer,
    CandidateDetailSerializer,
)
from .exam import (
    ExamListSerializer,
    ExamDetailSerializer,
    CandidateExamSerializer,
    ExamResultSerializer,
)
from .question import (
    QuestionListSerializer,
    QuestionDetailSerializer,
    CandidateQuestionSerializer,
)
from .registration import (
    CandidateRegistrationSerializer,
    StaffRegistrationSerializer,
)
from .role import (
    CandidateRoleSerializer,
    StaffRoleSerializer,
)
from .score import (
    CandidateScoreSerializer,
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


__all__ = [
    # answer
    "CandidateAnswerSerializer",
    "CandidateAnswerBulkSerializer",
    # auth
    "VerifyEmailOTPSerializer",
    "ResendEmailOTPSerializer",
    "RequestPasswordChangeSerializer",
    "PasswordChangeOTPConfirmSerializer",
    "PasswordChangeSerializer",
    # candidate
    "MinimalCandidateSerializer",
    "CandidateListSerializer",
    "CandidateDetailSerializer",
    # exam
    "ExamListSerializer",
    "ExamDetailSerializer",
    "CandidateExamSerializer",
    "ExamResultSerializer",
    # question
    "QuestionListSerializer",
    "QuestionDetailSerializer",
    "CandidateQuestionSerializer",
    # registration
    "CandidateRegistrationSerializer",
    "StaffRegistrationSerializer",
    # role
    "CandidateRoleSerializer",
    "StaffRoleSerializer",
    # score
    "CandidateScoreSerializer",
    "SubmitScoreSerializer",
    "CandidateExamScoreSerializer",
    # staff
    "MinimalStaffSerializer",
    "StaffListSerializer",
    "StaffDetailSerializer",
    # user
    "UserSerializer",
    "MinimalUserSerializer",
    "UserVerificationStatusSerializer",
    "UserVerificationUploadSerializer",
    "UserVerificationActionSerializer",
    "UserVerificationListSerializer",
]