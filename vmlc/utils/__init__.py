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
from ..utils.feature import ToggleFeatureFlagView
from .query_filters import (
    filter_candidates,
    filter_staffs,
    filter_questions,
    ExamFilter,
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
    # feature
    "ToggleFeatureFlagView",
    # query_filters
    "filter_candidates",
    "filter_staffs",
    "filter_questions",
    "ExamFilter",
]
