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


class InvalidTokenError(VMLCException):
    status_code = 401
    default_detail = "Token is invalid or expired."
    default_code = "invalid_token"
