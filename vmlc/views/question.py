import logging

from django.utils.decorators import method_decorator
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.settings import api_settings

from ..models import Question
from ..permissions import VerifiedModeratorPermissions
from ..serializers import QuestionListSerializer, QuestionDetailSerializer
from ..utils.swagger_schemas import (
    api_key,
    bearer_auth,
    question_list_response_schema,
    question_detail_request_body,
    question_detail_response_schema,
    error_response_400,
    error_response_401,
    error_response_403,
    error_response_404,
)
from ..utils.query_filters import filter_questions

logger = logging.getLogger(__name__)


@method_decorator(
    name="get",
    decorator=swagger_auto_schema(
        operation_summary="List Questions",
        operation_description="List all questions.",
        responses={
            200: question_list_response_schema,
            401: error_response_401,
            403: error_response_403,
        },
        tags=["Questions"],
        manual_parameters=[api_key, bearer_auth],
    ),
)
@method_decorator(
    name="post",
    decorator=swagger_auto_schema(
        operation_summary="Create Question",
        operation_description="Create a new question.",
        request_body=question_detail_request_body,
        responses={
            201: question_detail_response_schema,
            400: error_response_400,
            401: error_response_401,
            403: error_response_403,
        },
        tags=["Questions"],
        manual_parameters=[api_key, bearer_auth],
    ),
)
class QuestionListView(ListCreateAPIView):
    """
    List all questions or create a new question.

    - GET: Returns a paginated and filtered list of questions.
    - POST: Creates a new question from provided data.

    Permissions:
        - Only accessible to verified staff with role: moderator, admin, or superadmin.
    """

    permission_classes = VerifiedModeratorPermissions
    pagination_class = api_settings.DEFAULT_PAGINATION_CLASS

    def get_serializer_class(self):
        """
        Use a more detailed serializer for creation.
        """
        if self.request.method == "POST":
            return QuestionDetailSerializer
        return QuestionListSerializer

    def get_queryset(self):
        """
        Optimizes the queryset by prefetching related user data.
        """
        logger.info(
            f"QuestionListView: request from user {self.request.user.id} with query params: {self.request.query_params}"
        )
        queryset = (
            Question.objects.filter(is_active=True)
            .select_related("created_by__user")
            .order_by("-date_created")
        )
        return filter_questions(queryset, self.request.query_params)

    def perform_create(self, serializer):
        """
        Set the `created_by` field to the current staff user.
        """
        # IsVerifiedStaff permission ensures staff_profile exists
        serializer.save(created_by=self.request.user.staff_profile)
        logger.info(
            "Question created by user %s with data: %s",
            self.request.user.id,
            serializer.data,
        )


@method_decorator(
    name="get",
    decorator=swagger_auto_schema(
        operation_summary="Get Question Details",
        operation_description="Retrieve a question.",
        responses={
            200: question_detail_response_schema,
            401: error_response_401,
            403: error_response_403,
            404: error_response_404,
        },
        tags=["Questions"],
        manual_parameters=[api_key, bearer_auth],
    ),
)
@method_decorator(
    name="put",
    decorator=swagger_auto_schema(
        operation_summary="Update Question",
        operation_description="Update a question.",
        request_body=question_detail_request_body,
        responses={
            200: question_detail_response_schema,
            400: error_response_400,
            401: error_response_401,
            403: error_response_403,
            404: error_response_404,
        },
        tags=["Questions"],
        manual_parameters=[api_key, bearer_auth],
    ),
)
@method_decorator(
    name="patch",
    decorator=swagger_auto_schema(
        operation_summary="Partially Update Question",
        operation_description="Partially update a question.",
        request_body=question_detail_request_body,
        responses={
            200: question_detail_response_schema,
            400: error_response_400,
            401: error_response_401,
            403: error_response_403,
            404: error_response_404,
        },
        tags=["Questions"],
        manual_parameters=[api_key, bearer_auth],
    ),
)
@method_decorator(
    name="delete",
    decorator=swagger_auto_schema(
        operation_summary="Delete Question",
        operation_description="Delete a question.",
        responses={
            204: openapi.Response("Question deleted successfully."),
            401: error_response_401,
            403: error_response_403,
            404: error_response_404,
        },
        tags=["Questions"],
        manual_parameters=[api_key, bearer_auth],
    ),
)
class QuestionDetailView(RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete a specific question.

    - GET: Returns details of a specific question.
    - PUT/PATCH: Updates the question data.
    - DELETE: Deletes the question.

    Permissions:
        - Only accessible to staff with role: moderator, admin, or superadmin.
    """

    permission_classes = VerifiedModeratorPermissions
    serializer_class = QuestionDetailSerializer
    queryset = (
        Question.objects.filter(is_active=True)
        .select_related("created_by__user", "updated_by__user")
        .all()
    )
    lookup_url_kwarg = "question_id"

    def perform_update(self, serializer):
        """
        Set the `updated_by` field to the current staff user.
        """
        serializer.save(updated_by=self.request.user.staff_profile)
        logger.info(
            "Question %s updated by %s with data: %s",
            serializer.instance.id,
            self.request.user.id,
            serializer.data,
        )

    def perform_destroy(self, instance):
        """
        Soft-delete the question by setting `is_active` to False and log the action.
        """
        question_id = instance.id
        instance.is_active = False
        instance.save()
        logger.info("Question %s deleted by user %s", question_id, self.request.user.id)
