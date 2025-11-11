"""
Custom exception classes for the VMLC project.
"""

from rest_framework.exceptions import APIException


class VMLCException(APIException):
    """
    Base class for VMLC exceptions.
    Subclasses should provide a `default_detail` and `status_code`.
    """

    pass


class AuthenticationFailed(VMLCException):
    status_code = 401
    default_detail = "Incorrect authentication credentials."
    default_code = "authentication_failed"


class NotAuthenticated(VMLCException):
    status_code = 401
    default_detail = "Authentication credentials were not provided."
    default_code = "not_authenticated"


class PermissionDenied(VMLCException):
    status_code = 403
    default_detail = "You do not have permission to perform this action."
    default_code = "permission_denied"


class NotFound(VMLCException):
    status_code = 404
    default_detail = "Not found."
    default_code = "not_found"


class ValidationError(VMLCException):
    status_code = 400
    default_detail = "Invalid input."
    default_code = "invalid"


class NoRecipientsFoundError(ValidationError):
    """
    Raised when a broadcast operation finds no recipients for a given target.
    """

    default_detail = "No recipients found for the specified target."
    default_code = "no_recipients_found"


class InvalidMediumError(ValidationError):
    """Raised when an unknown broadcast medium is specified."""

    default_detail = "The specified broadcast medium is invalid."
    default_code = "invalid_medium"


class InvalidTokenError(VMLCException):
    status_code = 401
    default_detail = "Token is invalid or expired."
    default_code = "invalid_token"


class ServerError(VMLCException):
    status_code = 500
    default_detail = "Internal server error."
    default_code = "server_error"
