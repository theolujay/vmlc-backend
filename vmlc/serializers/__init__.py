"""
This package contains all the serializers for the API.
"""

from .answer import (
    CandidateAnswerSerializer,
    CandidateAnswerBulkSerializer,
)
from identity.serializers.auth import (
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
from .question import (
    QuestionListSerializer,
    QuestionDetailSerializer,
    CandidateQuestionSerializer,
)
from .registration import (
    CandidateRegistrationSerializer,
    StaffRegistrationSerializer,
    StaffInviteSerializer,
)
from ..v2.serializers.registration import RegistrationV2Serializer
from .staff import (
    MinimalStaffSerializer,
    StaffListSerializer,
    StaffDetailSerializer,
)
from .user import (
    UserSerializer,
    MinimalUserSerializer,
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
    # question
    "QuestionListSerializer",
    "QuestionDetailSerializer",
    "CandidateQuestionSerializer",
    # registration
    "CandidateRegistrationSerializer",
    "StaffRegistrationSerializer",
    "StaffInviteSerializer",
    "RegistrationV2Serializer",
    # staff
    "MinimalStaffSerializer",
    "StaffListSerializer",
    "StaffDetailSerializer",
    # user
    "UserSerializer",
    "MinimalUserSerializer",
    "UserProfileDetailSerializer",
    "UserProfileListSerializer",
]
