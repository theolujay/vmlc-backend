"""
Authentication-related API views for login, logout, and registration.
"""

from django.urls.exceptions import NoReverseMatch
from django.views.decorators.cache import cache_page

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.reverse import reverse

@cache_page(60 * 15)
@api_view(["GET"])
@permission_classes([AllowAny])
def api_root(request, format=None):
    """API entry point with discoverable endpoints"""

    def generate_url_with_placeholder(name, param_name, is_uuid=False):
        """Generate URL with placeholder for dynamic endpoints"""
        try:
            # Use a dummy UUID for uuid params, otherwise use an integer.
            dummy_id = "00000000-0000-0000-0000-000000000000" if is_uuid else 99999
            url = reverse(
                name,
                kwargs={param_name: dummy_id},
                request=request,
                format=format,
            )
            return url.replace(str(dummy_id), f"<{param_name}>")
        except NoReverseMatch:
            return None

    def safe_reverse(name, **kwargs):
        """Safely generate URLs, return None if route doesn't exist"""
        try:
            return reverse(name, request=request, format=format, **kwargs)
        except NoReverseMatch:
            return None

    return Response(
        {   
            "api-root": safe_reverse("v1:api-root"),
            "authentication": {
                "login": safe_reverse("v1:api-login"),
                "logout": safe_reverse("v1:api-logout"),
                "token_refresh": safe_reverse("v1:token-refresh"),
            },
            "registration": {
                "toggle_candidate": safe_reverse(
                    "v1:api-toggle-candidate-registration"
                ),
                "toggle_staff": safe_reverse("v1:api-toggle-staff-registration"),
                "candidate": safe_reverse("v1:api-register-candidate"),
                "staff": safe_reverse("v1:api-register-staff"),
            },
            "email_verification": {
                "verify_otp": safe_reverse("v1:verify-email-otp"),  
                "resend_otp": safe_reverse("v1:resend-email-otp"),  
            },
            "password_change": {
                "request": safe_reverse("v1:api-request-password-change"),  
                "confirm": safe_reverse("v1:api-verify-password-change-otp"),  
                "change": safe_reverse("v1:api-password-change"),
                "resend_otp": safe_reverse("v1:api-resend-password-change-otp"),  
            },
            "candidates": {
                "collection": safe_reverse("v1:api-candidate-list"),
                # "me": safe_reverse("v1:api-candidate-me"),
                "detail": generate_url_with_placeholder(
                    "v1:api-candidate-detail", "candidate_id", is_uuid=True
                ),
                "actions": {
                    "assign-role": generate_url_with_placeholder(
                        "v1:api-candidate-role-assign", "candidate_id", is_uuid=True
                    ),
                    "scores": generate_url_with_placeholder(
                        "v1:api-candidate-scores", "candidate_id", is_uuid=True
                    ),
                    "exam-history": generate_url_with_placeholder(
                        "v1:api-candidate-exam-history",
                        "candidate_id",
                        is_uuid=True,
                    ),
                },
            },
            "staff": {
                "collection": safe_reverse("v1:api-staff-list"),
                # "me": safe_reverse("v1:api-staff-me"),
                "detail": generate_url_with_placeholder(
                    "v1:api-staff-detail", "staff_id", is_uuid=True
                ),
                "actions": {
                    "assign_role": generate_url_with_placeholder(
                        "v1:api-staff-role-assign", "staff_id", is_uuid=True
                    ),
                },
            },
            "exams": {
                "collection": safe_reverse("v1:api-exam-list"),
                "detail": generate_url_with_placeholder(
                    "v1:api-exam-detail", "exam_id"
                ),
                "questions": generate_url_with_placeholder(
                    "v1:api-exam-questions", "exam_id"
                ),
                "results": generate_url_with_placeholder(
                    "v1:api-exam-results", "exam_id"
                ),
                "candidate-take-exam": generate_url_with_placeholder(
                    "v1:api-take-exam", "exam_id"
                ),
                "submission": {
                    "submit-exam-score": generate_url_with_placeholder(
                        "v1:api-submit-exam-score", "exam_id"
                    ),
                    "submit-exam-answers": generate_url_with_placeholder(
                        "v1:api-submit-exam-answers", "exam_id"
                    ),
                },
            },
            "scores": {
                "publish": safe_reverse("v1:api-publish-scores"),
            },
            "questions": {
                "collection": safe_reverse("v1:api-question-list"),
                "detail": generate_url_with_placeholder(
                    "v1:api-question-detail", "question_id"
                ),
            },
            "leaderboard": {
                "toggle": safe_reverse("v1:api-toggle-leaderboard"),
                "publish": safe_reverse("v1:api-publish-leaderboard"),
                "load": safe_reverse("v1:api-load-leaderboard"),
            },
            "dashboard": {
                "candidate": safe_reverse("v1:api-candidate-dashboard"),
                "staff": safe_reverse("v1:api-staff-dashboard"),
            },
            "user-accounts": {
                "account-management": safe_reverse("v1:api-account-management"),
                "account-management-detail": generate_url_with_placeholder(
                    "v1:api-account-management-detail", "user_id", is_uuid=True
                ),
            },
            "user_verification": {
                "status": safe_reverse("v1:user-verification-status"),
                "upload": safe_reverse("v1:user-verification-upload"),
                "list": safe_reverse("v1:user-verification-list-admin"),  
                "documents": {
                    "own": generate_url_with_placeholder(
                        "v1:user-verification-document", "file_type"
                    ),
                    "admin": generate_url_with_placeholder(
                        "v1:user-verification-document-admin",  
                        "file_type", # TODO: accomodate user_id
                    ),
                },
            },
        }
    )