from rest_framework import status
from rest_framework.views import exception_handler

def custom_exception_handler(exc, context):
    """
    Custom exception handler to standardize error responses across the project.
    """
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)

    if response is not None:
        # Handle Validation Errors (400)
        if response.status_code == status.HTTP_400_BAD_REQUEST:
            # Wrap the standard DRF error response
            response.data = {
                "status": "error",
                "message": "Validation failed.",
                "errors": response.data
            }

    return response