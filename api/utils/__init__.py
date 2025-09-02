"""
This package contains all the utility functions for the API.
"""

from .auth import (
    generate_otp,
    can_resend_otp,
    send_otp_to_email,
    resend_otp_to_email,
    send_password_change_otp,
    verify_otp_for_password_change,
)
from .dashboard_utils import (
    get_candidate_dashboard_data,
    get_staff_dashboard_data,
)
from .query_filters import (
    filter_candidates,
    filter_staffs,
    filter_questions,
    ExamFilter,
)
from .user import (
    validate_role_for_serializer,
    get_user_profile,
)


__all__ = [
    # auth
    "generate_otp",
    "can_resend_otp",
    "send_otp_to_email",
    "resend_otp_to_email",
    "send_password_change_otp",
    "verify_otp_for_password_change",
    # dashboard_utils
    "get_candidate_dashboard_data",
    "get_staff_dashboard_data",
    # query_filters
    "filter_candidates",
    "filter_staffs",
    "filter_questions",
    "ExamFilter",
    # user
    "validate_role_for_serializer",
    "get_user_profile",
]
