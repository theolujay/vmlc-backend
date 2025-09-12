import logging

from django.urls.exceptions import NoReverseMatch
from django.views.decorators.cache import cache_page
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.reverse import reverse


logger = logging.getLogger(__name__)


@cache_page(60 * 15)
@api_view(["GET"])
@permission_classes([AllowAny])
def root(request, format=None):
    """API entry point with discoverable endpoints"""
    logger.info(
        f"API root accessed by {request.user if request.user.is_authenticated else 'anonymous'} from {request.META.get('REMOTE_ADDR')}"
    )

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
            logger.warning(f"No reverse match for URL name: {name}")
            return None

    def safe_reverse(name, **kwargs):
        """Safely generate URLs, return None if route doesn't exist"""
        try:
            return reverse(name, request=request, format=format, **kwargs)
        except NoReverseMatch:
            logger.warning(f"No reverse match for URL name: {name}")
            return None

    return Response(
        {
            "root": safe_reverse("v1:root"),
            "authentication": {
                "login": safe_reverse("v1:login"),
                "logout": safe_reverse("v1:logout"),
                "token_refresh": safe_reverse("v1:token-refresh"),
            },
            "registration": {
                "toggle_candidate": safe_reverse("v1:toggle-candidate-registration"),
                "toggle_staff": safe_reverse("v1:toggle-staff-registration"),
                "candidate": safe_reverse("v1:register-candidate"),
                "staff": safe_reverse("v1:register-staff"),
            },
            "email_verification": {
                "verify_otp": safe_reverse("v1:verify-email-otp"),
                "resend_otp": safe_reverse("v1:resend-email-otp"),
            },
            "password_change": {
                "request": safe_reverse("v1:request-password-change"),
                "confirm": safe_reverse("v1:verify-password-change-otp"),
                "change": safe_reverse("v1:password-change"),
                "resend_otp": safe_reverse("v1:resend-password-change-otp"),
            },
            "candidates": {
                "collection": safe_reverse("v1:candidate-list"),
                # "me": safe_reverse("v1:candidate-me"),
                "detail": generate_url_with_placeholder(
                    "v1:candidate-detail", "candidate_id", is_uuid=True
                ),
                "actions": {
                    "assign-role": generate_url_with_placeholder(
                        "v1:candidate-role-assign", "candidate_id", is_uuid=True
                    ),
                    "scores": generate_url_with_placeholder(
                        "v1:candidate-scores", "candidate_id", is_uuid=True
                    ),
                    "exam-history": generate_url_with_placeholder(
                        "v1:candidate-exam-history",
                        "candidate_id",
                        is_uuid=True,
                    ),
                },
            },
            "staff": {
                "collection": safe_reverse("v1:staff-list"),
                # "me": safe_reverse("v1:staff-me"),
                "detail": generate_url_with_placeholder(
                    "v1:staff-detail", "staff_id", is_uuid=True
                ),
                "actions": {
                    "assign_role": generate_url_with_placeholder(
                        "v1:staff-role-assign", "staff_id", is_uuid=True
                    ),
                },
            },
            "exams": {
                "collection": safe_reverse("v1:exam-list"),
                "detail": generate_url_with_placeholder("v1:exam-detail", "exam_id"),
                "questions": generate_url_with_placeholder(
                    "v1:exam-questions", "exam_id"
                ),
                "results": generate_url_with_placeholder("v1:exam-results", "exam_id"),
                "candidate-take-exam": generate_url_with_placeholder(
                    "v1:take-exam", "exam_id"
                ),
                "submission": {
                    "submit-exam-score": generate_url_with_placeholder(
                        "v1:submit-exam-score", "exam_id"
                    ),
                    "submit-exam-answers": generate_url_with_placeholder(
                        "v1:submit-exam-answers", "exam_id"
                    ),
                },
            },
            "scores": {
                "publish": safe_reverse("v1:publish-scores"),
            },
            "questions": {
                "collection": safe_reverse("v1:question-list"),
                "detail": generate_url_with_placeholder(
                    "v1:question-detail", "question_id"
                ),
            },
            "leaderboard": {
                "toggle": safe_reverse("v1:toggle-leaderboard"),
                "publish": safe_reverse("v1:publish-leaderboard"),
                "load": safe_reverse("v1:load-leaderboard"),
            },
            "dashboard": {
                "candidate": safe_reverse("v1:candidate-dashboard"),
                "staff": safe_reverse("v1:staff-dashboard"),
            },
            "user-accounts": {
                "account-management": safe_reverse("v1:account-management"),
                "account-management-detail": generate_url_with_placeholder(
                    "v1:account-management-detail", "user_id", is_uuid=True
                ),
            },
            "user_verification": {
                "status": safe_reverse("v1:user-verification-status"),
                "upload": safe_reverse("v1:user-verification-upload"),
                "list": safe_reverse("v1:user-verification-list"),
                "action": generate_url_with_placeholder(
                    "v1:user-verification-action", "user_id", is_uuid=True
                ),
                "documents": {
                    "own": generate_url_with_placeholder(
                        "v1:user-verification-document", "file_type"
                    ),
                    "admin": generate_url_with_placeholder(
                        "v1:user-verification-document-admin",
                        "file_type",  # TODO: accomodate user_id
                    ),
                },
            },
        }
    )
