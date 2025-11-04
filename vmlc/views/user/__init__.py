from .verification import (
    UserVerificationStatusView,
    UserVerificationUploadView,
    UserVerificationDocumentView,
    UserVerificationListView,
    UserVerificationActionView,
)
from .management import (
    StaffInviteView,
    CandidateInviteView,
    AccountManagementView,
)

__all__ = [
    # verification
    "UserVerificationStatusView",
    "UserVerificationUploadView",
    "UserVerificationDocumentView",
    "UserVerificationListView",
    "UserVerificationActionView",
    # management
    "AccountManagementView",
    "StaffInviteView",
    "CandidateInviteView",
]