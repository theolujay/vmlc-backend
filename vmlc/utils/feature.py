import logging

from django.core.exceptions import ImproperlyConfigured
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

# from channels.db import database_sync_to_async

from ..models import FeatureFlag
from ..permissions import HasMinimumStaffRole
from .swagger_schemas import api_key, bearer_auth


logger = logging.getLogger(__name__)


class ToggleFeatureFlagView(APIView):
    """
    A generic view to toggle a boolean feature flag.
    Subclasses must specify `feature_flag_key` and `permission_classes`.
    """

    swagger_schema = None
    permission_classes = [
        IsAuthenticated,
        HasMinimumStaffRole("manager"),
    ]
    feature_flag_key = None

    # @swagger_auto_schema(
    #     operation_description="Toggle a feature flag.",
    #     manual_parameters=[api_key, bearer_auth],
    # )
    def post(self, request, *args, **kwargs):
        return self._toggle_feature_flag(request, *args, **kwargs)

    def _toggle_feature_flag(self, request, *args, **kwargs):
        logger.info(
            f"{self.__class__.__name__}: request from user {request.user.id} with data: {request.data}"
        )
        if not self.feature_flag_key:
            logger.error(f"{self.__class__.__name__} is missing a feature_flag_key.")
            raise ImproperlyConfigured(
                f"{self.__class__.__name__} is missing a feature_flag_key."
            )

        visible_flag = request.data.get("open", False)
        obj, created = FeatureFlag.objects.get_or_create(
            key=self.feature_flag_key, defaults={"value": visible_flag}
        )

        if not created:
            obj.value = visible_flag
            obj.save()

        logger.info(
            "Feature flag '%s' toggled to %s by user %s.",
            self.feature_flag_key,
            obj.value,
            request.user.id,
        )

        FEATURE_FLAG_MESSAGES = {
            "candidate_registration_open": {
                True: "Candidate registration is now open.",
                False: "Candidate registration is now closed.",
            },
            "staff_registration_open": {
                True: "Staff registration is now open.",
                False: "Staff registration is now closed.",
            },
            "leaderboard_visible": {
                True: "Leaderboard is now visible.",
                False: "Leaderboard is now hidden.",
            },
        }

        message_config = FEATURE_FLAG_MESSAGES.get(self.feature_flag_key)
        if message_config:
            message = message_config[obj.value]
        else:
            feature_name = self.feature_flag_key.replace("_", " ").title()
            status_text = "enabled" if obj.value else "disabled"
            message = f"'{feature_name}' is now {status_text}."

        return Response(
            {"message": message},
            status=status.HTTP_200_OK,
        )
