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

    def generate_url_with_placeholder(name, placeholder, param):
        """Generate URL with placeholder for dynamic endpoints"""
        try:
            dummy_id = 99999
            url = reverse(
                name,
                kwargs={param: dummy_id},
                request=request,
                format=format,
            )
            return url.replace(str(dummy_id), placeholder)
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
            "authentication": {
                "login": safe_reverse("v1:api-login"),
                "logout": safe_reverse("v1:api-logout"),
                "token": {
                    "obtain": safe_reverse("v1:token-obtain-pair"),
                    "refresh": safe_reverse("v1:token-refresh"),
                },
            },
            "registration": {
                "toggle_candidate": safe_reverse(
                    "v1:api-toggle-candidate-registration"
                ),
                "toggle_staff": safe_reverse("v1:api-toggle-staff-registration"),
                "candidate": safe_reverse("v1:api-register-candidate"),
                "staff": safe_reverse("v1:api-register-staff"),
            },
            "candidates": {
                "collection": safe_reverse("v1:api-candidate-list"),
                "me": safe_reverse("v1:api-candidate-me"),
                "detail": generate_url_with_placeholder(
                    "v1:api-candidate-detail", "<candidate_id>", "candidate_id"
                ),
                "actions": {
                    "assign-role": generate_url_with_placeholder(
                        "v1:api-candidate-role-assign", "<candidate_id>", "candidate_id"
                    ),
                    "scores": generate_url_with_placeholder(
                        "v1:api-candidate-scores", "<candidate_id>", "candidate_id"
                    ),
                    "exam-history": generate_url_with_placeholder(
                        "v1:api-candidate-exam-history",
                        "<candidate_id>",
                        "candidate_id",
                    ),
                },
            },
            "staff": {
                "collection": safe_reverse("v1:api-staff-list"),
                "me": safe_reverse("v1:api-staff-me"),
                "detail": generate_url_with_placeholder(
                    "v1:api-staff-detail", "<staff_id>", "staff_id"
                ),
                "actions": {
                    "assign_role": generate_url_with_placeholder(
                        "v1:api-staff-role-assign", "<staff_id>", "staff_id"
                    ),
                },
            },
            "exams": {
                "collection": safe_reverse("v1:api-exam-list"),
                "detail": generate_url_with_placeholder(
                    "v1:api-exam-detail", "<exam_id>", "exam_id"
                ),
                "questions": generate_url_with_placeholder(
                    "v1:api-exam-questions", "<exam_id>", "exam_id"
                ),
                "candidate-take-exam": generate_url_with_placeholder(
                    "v1:api-take-exam", "<exam_id>", "exam_id"
                ),
                "submission": {
                    "submit-exam-score": generate_url_with_placeholder(
                        "v1:api-submit-exam-score", "<exam_id>", "exam_id"
                    ),
                    "submit-exam-answers": generate_url_with_placeholder(
                        "v1:api-submit-exam-answers", "<exam_id>", "exam_id"
                    ),
                },
            },
            "questions": {
                "collection": safe_reverse("v1:api-question-list"),
                "detail": generate_url_with_placeholder(
                    "v1:api-question-detail", "<question_id>", "question_id"
                ),
            },
            "dashboard": {
                "candidate": safe_reverse("v1:api-candidate-dashboard"),
                "staff": safe_reverse("v1:api-staff-dashboard"),
            },
            "user-accounts": {
                "account-management": safe_reverse("v1:api-account-management"),
                "account-management-detail": generate_url_with_placeholder(
                    "v1:api-account-management-detail", "<user_id>", "user_id"
                ),
            },
            "leaderboard": {
                "toggle": safe_reverse("v1:api-toggle-leaderboard"),
                "publish": safe_reverse("v1:api-publish-leaderboard"),
                "load": safe_reverse("v1:api-load-leaderboard"),
            },
        }
    )
