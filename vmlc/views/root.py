import logging

from django.urls.exceptions import NoReverseMatch
from django.views.decorators.cache import cache_page
from rest_framework.decorators import api_view, permission_classes

from rest_framework.response import Response
from rest_framework.reverse import reverse

from ..permissions import HasXAPIKey

logger = logging.getLogger(__name__)


@cache_page(60 * 15)
@api_view(["GET"])
@permission_classes([HasXAPIKey])
def root(request, format_kw=None):
    """API entry point with discoverable endpoints"""
    logger.info(
        f"API root accessed by {request.user if request.user.is_authenticated else 'anonymous'} from {request.META.get('REMOTE_ADDR')}"
    )

    def generate_url_with_placeholder(name, params):
        """
        Generate URL with placeholders for dynamic endpoints.
        `params` is a dict of param_name: type ('uuid', 'int', 'str').
        """
        try:
            dummy_values = {
                "uuid": "00000000-0000-0000-0000-000000000000",
                "int": 99999,
            }
            kwargs = {}
            replacements = {}
            for param_name, param_type in params.items():
                dummy_value = dummy_values.get(param_type, f"placeholder_{param_name}")
                kwargs[param_name] = dummy_value
                replacements[str(dummy_value)] = f"<{param_name}>"

            url = reverse(name, kwargs=kwargs, request=request, format=format_kw)
            for old, new in replacements.items():
                url = url.replace(old, new)
            return url
        except NoReverseMatch:
            logger.warning(f"No reverse match for URL name: {name}")
            return None

    def safe_reverse(name, **kwargs):
        """Safely generate URLs, return None if route doesn't exist"""
        try:
            return reverse(name, request=request, format=format_kw, **kwargs)
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
                    "v1:candidate-detail", {"candidate_id": "uuid"}
                ),
                "actions": {
                    "assign-role": generate_url_with_placeholder(
                        "v1:candidate-role-assign", {"candidate_id": "uuid"}
                    ),
                    "scores": generate_url_with_placeholder(
                        "v1:candidate-scores", {"candidate_id": "uuid"}
                    ),
                    "exam-history": generate_url_with_placeholder(
                        "v1:candidate-exam-history",
                        {"candidate_id": "uuid"},
                    ),
                },
            },
            "staff": {
                "collection": safe_reverse("v1:staff-list"),
                # "me": safe_reverse("v1:staff-me"),
                "detail": generate_url_with_placeholder(
                    "v1:staff-detail", {"staff_id": "uuid"}
                ),
                "actions": {
                    "assign_role": generate_url_with_placeholder(
                        "v1:staff-role-assign", {"staff_id": "uuid"}
                    ),
                },
            },
            "exams": {
                "collection": safe_reverse("v1:exam-list"),
                "detail": generate_url_with_placeholder(
                    "v1:exam-detail", {"exam_id": "int"}
                ),
                "questions": generate_url_with_placeholder(
                    "v1:exam-questions", {"exam_id": "int"}
                ),
                "results": generate_url_with_placeholder(
                    "v1:exam-results", {"exam_id": "int"}
                ),
                "candidate-take-exam": generate_url_with_placeholder(
                    "v1:take-exam", {"exam_id": "int"}
                ),
                "submission": {
                    "submit-exam-score": generate_url_with_placeholder(
                        "v1:submit-exam-score", {"exam_id": "int"}
                    ),
                    "submit-exam-answers": generate_url_with_placeholder(
                        "v1:submit-exam-answers", {"exam_id": "int"}
                    ),
                },
            },
            "scores": {
                "publish": safe_reverse("v1:publish-scores"),
            },
            "questions": {
                "collection": safe_reverse("v1:question-list"),
                "detail": generate_url_with_placeholder(
                    "v1:question-detail", {"question_id": "int"}
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
                    "v1:account-management-detail", {"user_id": "uuid"}
                ),
            },
            "user_verification": {
                "status": safe_reverse("v1:user-verification-status"),
                "upload": safe_reverse("v1:user-verification-upload"),
                "list": safe_reverse("v1:user-verification-list"),
                "action": generate_url_with_placeholder(
                    "v1:user-verification-action", {"user_id": "uuid"}
                ),
                "documents": {
                    "own": generate_url_with_placeholder(
                        "v1:user-verification-document", {"file_type": "str"}
                    ),
                    "admin": generate_url_with_placeholder(
                        "v1:user-verification-document-admin",
                        {"user_id": "uuid", "file_type": "str"},
                    ),
                },
            },
        }
    )
