from django.core.cache import cache
from vmlc.models import Staff, Candidate

SENSITIVE_FIELDS = {
    # User credentials
    'password', 'passwd', 'pwd', 'old_password', 'new_password',
    'password1', 'password2', 'password_confirmation',

    # API keys and tokens
    'secret', 'secret_key', 'api_secret',
    'token', 'access_token', 'refresh_token', 'auth_token',
    'api_key', 'apikey', 'private_key',
    'authorization', 'auth',

    # Payment and financial information
    'credit_card', 'card_number', 'cvv', 'cvc', 'cc_number',

    # Government-issued identifiers
    'ssn', 'social_security', 'national_id',

    # Session and security tokens
    'session_id', 'csrf_token', 'xsrf_token',

    # One-time passwords and PINs
    'otp', 'pin', 'mfa_code',

    # Personal identifiable information (PII)
    'email', 'first_name', 'last_name', 'phone', 'phone_number', 'date_of_birth', 'address',
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
    
    elif isinstance(data, (list, tuple)):
        # Sanitize each item in the list/tuple
        return type(data)(sanitize_data(item, redact_text) for item in data)
    
    else:
        # Primitive type (string, int, etc.) - return as is
        return data

def invalidate_all_staff_dashboards():
    """
    Invalidates the dashboard cache for all staff members.
    """
    for staff in Staff.objects.all():
        cache.delete(f"staff_dashboard_data_{staff.pk}")

def invalidate_all_candidate_records():
    """
    Invalidates Candidate.records cache for all candidate
    """
    for candidate in Candidate.objects.all():
        cache.delete(f"candidate_records_{candidate.pk}")