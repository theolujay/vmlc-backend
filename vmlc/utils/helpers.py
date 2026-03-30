from django.core.cache import cache
from identity.models import Staff, Candidate

SENSITIVE_FIELDS = {
    # User credentials
    "password",
    "passwd",
    "pwd",
    "old_password",
    "new_password",
    "password1",
    "password2",
    "password_confirmation",
    # API keys and tokens
    "secret",
    "secret_key",
    "api_secret",
    "token",
    "access_token",
    "refresh_token",
    "auth_token",
    "api_key",
    "apikey",
    "private_key",
    "authorization",
    "auth",
    # Payment and financial information
    "credit_card",
    "card_number",
    "cvv",
    "cvc",
    "cc_number",
    # Government-issued identifiers
    "ssn",
    "social_security",
    "national_id",
    # Session and security tokens
    "session_id",
    "csrf_token",
    "xsrf_token",
    # One-time passwords and PINs
    "otp",
    "pin",
    "mfa_code",
    # Personal identifiable information (PII)
    "email",
    "first_name",
    "last_name",
    "phone",
    "phone_number",
    "date_of_birth",
    "address",
}


def sanitize_data(data, redact_text="***REDACTED***"):
    """
    Recursively remove sensitive fields from data before logging.

    This function creates a copy of the data and replaces any values
    whose keys match SENSITIVE_FIELDS with a redacted placeholder.

    Args:
        data: Dictionary, list, or other data structure to sanitize
        redact_text: Text to replace sensitive values with

    Returns:
        Sanitized copy of the data safe for logging

    Example:
        >>> data = {'email': 'user@example.com', 'password': 'secret123'}
        >>> sanitize_data(data)
        {'email': 'user@example.com', 'password': '***REDACTED***'}
    """
    if isinstance(data, dict):
        sanitized = {}
        for key, value in data.items():
            # Check if this key contains sensitive data (case-insensitive)
            if key.lower() in SENSITIVE_FIELDS:
                sanitized[key] = redact_text
            else:
                # Recursively sanitize nested structures
                sanitized[key] = sanitize_data(value, redact_text)
        return sanitized

    if isinstance(data, (list, tuple)):
        return type(data)(sanitize_data(item, redact_text) for item in data)

    else:
        # Primitive type (string, int, etc.) - return as is
        return data


def invalidate_all_staff_dashboards():
    """
    Invalidates the dashboard cache for all staff members.
    """
    from vmlc.v2.utils import invalidate_staff_cache, invalidate_staff_dashboard

    invalidate_staff_dashboard()
    for staff in Staff.objects.all():
        invalidate_staff_cache(staff.user_id)
        # Legacy
        cache.delete(f"staff_dashboard_data_{staff.pk}")


def invalidate_all_candidate_dashboards():
    """
    Invalidates the dashboard cache for all candidates.
    """
    from vmlc.v2.utils import invalidate_candidate_cache

    for candidate in Candidate.objects.all():
        invalidate_candidate_cache(candidate.pk, candidate.user_id)
        # Legacy
        cache.delete(f"candidate_dashboard_{candidate.pk}")


def invalidate_all_candidate_records():
    """
    Invalidates Candidate.records cache for all candidate
    """
    for candidate in Candidate.objects.all():
        cache.delete(f"candidate_records_{candidate.pk}")


def invalidate_all_dashboard_caches():
    """
    Invalidates all dashboard caches for both staff and candidates.
    """
    invalidate_all_staff_dashboards()
    invalidate_all_candidate_dashboards()


import re
from logging import Filter


class SensitiveDataFilter(Filter):
    """
    Filter that redacts sensitive query parameters from log messages.

    Specifically targets URLs with sensitive query params like api_key, token,
    and authorization that may leak into access logs.
    """

    SENSITIVE_QUERY_PARAMS = {
        "api_key",
        "apikey",
        "token",
        "access_token",
        "refresh_token",
        "auth_token",
        "authorization",
        "bearer",
        "jwt",
        "secret",
        "secret_key",
        "password",
        "pwd",
        "session_id",
    }

    REDACTED = "***REDACTED***"

    def filter(self, record):
        if hasattr(record, "msg") and isinstance(record.msg, str):
            record.msg = self._redact_url_params(record.msg)
        if hasattr(record, "args") and record.args:
            record.args = tuple(
                self._redact_url_params(arg) if isinstance(arg, str) else arg
                for arg in record.args
            )
        return True

    def _redact_url_params(self, text: str) -> str:
        url_pattern = re.compile(
            r"(\?|&)({})=".format(
                "|".join(re.escape(p) for p in self.SENSITIVE_QUERY_PARAMS)
            ),
            re.IGNORECASE,
        )
        return url_pattern.sub(r"\1\2=***REDACTED***", text)
