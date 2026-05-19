import logging
import re


class SensitiveDataFilter(logging.Filter):
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
