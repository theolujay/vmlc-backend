import logging

from django.urls.exceptions import NoReverseMatch
from django.views.decorators.cache import cache_page, never_cache
from rest_framework.decorators import api_view, permission_classes

from rest_framework.response import Response
from rest_framework.reverse import reverse

from ..permissions import HasXAPIKey

logger = logging.getLogger(__name__)

@never_cache
# @cache_page(60 * 15)
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
            "root": safe_reverse("vmlc:root"),
            "authentication": {
                "login": safe_reverse("vmlc:login"),
                "logout": safe_reverse("vmlc:logout"),
                "token_refresh": safe_reverse("vmlc:token-refresh"),
            },
            "registration": {
                "toggle_candidate": safe_reverse("vmlc:toggle-candidate-registration"),
                "toggle_staff": safe_reverse("vmlc:toggle-staff-registration"),
                "candidate": safe_reverse("vmlc:register-candidate"),
                "staff": safe_reverse("vmlc:register-staff"),
            },
            "email_verification": {
                "verify_otp": safe_reverse("vmlc:verify-email-otp"),
                "resend_otp": safe_reverse("vmlc:resend-email-otp"),
            },
            "password_change": {
                "request": safe_reverse("vmlc:request-password-change"),
                "confirm": safe_reverse("vmlc:verify-password-change-otp"),
                "change": safe_reverse("vmlc:password-change"),
                "resend_otp": safe_reverse("vmlc:resend-password-change-otp"),
            },
            "candidates": {
                "collection": safe_reverse("vmlc:candidate-list"),
                # "me": safe_reverse("vmlc:candidate-me"),
                "detail": generate_url_with_placeholder(
                    "vmlc:candidate-detail", {"candidate_id": "uuid"}
                ),
                "actions": {
                    "assign-role": generate_url_with_placeholder(
                        "vmlc:candidate-role-assign", {"candidate_id": "uuid"}
                    ),
                    "scores": generate_url_with_placeholder(
                        "vmlc:candidate-scores", {"candidate_id": "uuid"}
                    ),
                    "exam-history": generate_url_with_placeholder(
                        "vmlc:candidate-exam-history",
                        {"candidate_id": "uuid"},
                    ),
                },
            },
            "staff": {
                "collection": safe_reverse("vmlc:staff-list"),
                # "me": safe_reverse("vmlc:staff-me"),
                "detail": generate_url_with_placeholder(
                    "vmlc:staff-detail", {"staff_id": "uuid"}
                ),
                "actions": {
                    "assign_role": generate_url_with_placeholder(
                        "vmlc:staff-role-assign", {"staff_id": "uuid"}
                    ),
                },
            },
            "exams": {
                "collection": safe_reverse("vmlc:exam-list"),
                "detail": generate_url_with_placeholder(
                    "vmlc:exam-detail", {"exam_id": "int"}
                ),
                "questions": generate_url_with_placeholder(
                    "vmlc:exam-questions", {"exam_id": "int"}
                ),
                "results": generate_url_with_placeholder(
                    "vmlc:exam-results", {"exam_id": "int"}
                ),
                "candidate-take-exam": generate_url_with_placeholder(
                    "vmlc:take-exam", {"exam_id": "int"}
                ),
                "submission": {
                    "submit-exam-score": generate_url_with_placeholder(
                        "vmlc:submit-exam-score", {"exam_id": "int"}
                    ),
                    "submit-exam-answers": generate_url_with_placeholder(
                        "vmlc:submit-exam-answers", {"exam_id": "int"}
                    ),
                },
            },
            "scores": {
                "publish": safe_reverse("vmlc:publish-scores"),
            },
            "questions": {
                "collection": safe_reverse("vmlc:question-list"),
                "detail": generate_url_with_placeholder(
                    "vmlc:question-detail", {"question_id": "int"}
                ),
            },
            "leaderboard": {
                "toggle": safe_reverse("vmlc:toggle-leaderboard"),
                "publish": safe_reverse("vmlc:publish-leaderboard"),
                "load": safe_reverse("vmlc:load-leaderboard"),
            },
            "dashboard": {
                "candidate": safe_reverse("vmlc:candidate-dashboard"),
                "staff": safe_reverse("vmlc:staff-dashboard"),
            },
            "user-accounts": {
                "account-management": safe_reverse("vmlc:account-management"),
                "account-management-detail": generate_url_with_placeholder(
                    "vmlc:account-management-detail", {"user_id": "uuid"}
                ),
            },
            "user_verification": {
                "status": safe_reverse("vmlc:user-verification-status"),
                "upload": safe_reverse("vmlc:user-verification-upload"),
                "list": safe_reverse("vmlc:user-verification-list"),
                "action": generate_url_with_placeholder(
                    "vmlc:user-verification-action", {"user_id": "uuid"}
                ),
                "documents": {
                    "own": generate_url_with_placeholder(
                        "vmlc:user-verification-document", {"file_type": "str"}
                    ),
                    "admin": generate_url_with_placeholder(
                        "vmlc:user-verification-document-admin",
                        {"user_id": "uuid", "file_type": "str"},
                    ),
                },
            },
        }
    )
