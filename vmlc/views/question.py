import logging

from django.db.models import Count, Q
from django.utils.decorators import method_decorator
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.views import APIView
from rest_framework import status

from ..models import Exam, Question
from ..permissions import VerifiedAdminPermissions, VerifiedModeratorPermissions
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

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        meta = queryset.aggregate(
            total_questions=Count("id"),
            hard_questions_count=Count(
                "id", filter=Q(difficulty=Question.Difficulty.HARD)
            ),
            medium_questions_count=Count(
                "id", filter=Q(difficulty=Question.Difficulty.MEDIUM)
            ),
            easy_questions_count=Count(
                "id", filter=Q(difficulty=Question.Difficulty.EASY)
            ),
        )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data["meta"] = meta
            response.data["list"] = response.data.pop("results")
            del response.data["count"]
            return response

        serializer = self.get_serializer(queryset, many=True)
        return Response({"meta": meta, "list": serializer.data})

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
            Question.objects.filter(is_archived=False)
            .select_related("created_by__user")
            .order_by("-created_at")
        )
        return filter_questions(queryset, self.request.query_params)

    def perform_create(self, serializer):
        """
        Create question and optionally add it to specified exams.
        Set the `created_by` field to the current staff user.
        """
        question = serializer.save(created_by=self.request.user.staff_profile)
        logger.info(
            "Question created by user %s with data: %s",
            self.request.user.id,
            serializer.data,
        )
        
        add_to_exams=self.request.data.get("add_to_exams", None)
        if add_to_exams:
            if not isinstance(add_to_exams, list):
                logger.warning(
                    "add_to_exams should be a list, got %s",
                    type(add_to_exams).__name__
                )
                return
            added_count = 0
            failed_exams = []
            for exam_id in add_to_exams:
                try:
                    exam = Exam.objects.get(id=exam_id)
                    exam.questions.add(question)
                    added_count += 1
                    logger.info(
                        "Question %s added to exam %s",
                        question.id,
                        exam.id,
                        exam.title
                    )
                except Exam.DoesNotExist:
                    failed_exams.append(exam_id)
                    logger.warning(
                        "Cannot add question %s to exam %s - exam does not exist",
                        question.id,
                        exam_id
                    )
                except Exception as e:
                    failed_exams.append(exam_id)
                    logger.error(
                        "Error adding question %s to exam %s: %s",
                        question.id,
                        exam_id,
                        str(e)
                    )
            if added_count > 0:
                logger.info(
                    "Question %s successfully added to %s exams(s)",
                    question.id,
                    added_count
                )
            if failed_exams:
                logger.warning(
                    "Failed to add question %s to %s exams: %s",
                    question.id,
                    failed_exams
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
        Question.objects.filter(is_archived=False)
        .select_related("created_by__user", "updated_by__user")
        .all()
    )
    lookup_url_kwarg = "question_id"

    def perform_update(self, serializer):
        """
        Set the `updated_by` field to the current staff user.
        Optionally add/remove question from exams (admin only).
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
        Archive the question by setting `is_archived` to True and log the action.
        """
        question_id = instance.id
        instance.archive()
        logger.info("Question %s removed by user %s", question_id, self.request.user.id)

@method_decorator(
    name="post",
    decorator=swagger_auto_schema(
        operation_summary="Manage Question-Exam Associations",
        operation_description="Add or remove a question from exams. Admin only.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'add_to_exams': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(type=openapi.TYPE_INTEGER),
                    description='List of exam IDs to add question to'
                ),
                'remove_from_exams': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(type=openapi.TYPE_INTEGER),
                    description='List of exam IDs to remove question from'
                ),
            }
        ),
        responses={
            200: openapi.Response("Exam associations updated successfully."),
            400: error_response_400,
            401: error_response_401,
            403: error_response_403,
            404: error_response_404,
        },
        tags=["Questions"],
        manual_parameters=[api_key, bearer_auth],
    ),
)
class QuestionExamAssociationView(APIView):
    """
    Manage a question's exam associations.
    
    POST: Add or remove question from specified exams.
    
    Permissions:
        - Only accessible to verified staff with role: admin or superadmin.
    """
    
    permission_classes = VerifiedAdminPermissions
    
    def post(self, request, question_id):
        """
        Add or remove question from exams.
        """
        try:
            question = Question.objects.get(id=question_id, is_archived=False)
        except Question.DoesNotExist:
            return Response(
                {"error": "Question not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        add_to_exams = request.data.get("add_to_exams", [])
        remove_from_exams = request.data.get("remove_from_exams", [])
        
        results = {
            "question_id": question.id,
            "added": [],
            "removed": [],
            "failed_additions": [],
            "failed_removals": []
        }
        
        # Add to exams
        if add_to_exams:
            if isinstance(add_to_exams, list):
                for exam_id in add_to_exams:
                    try:
                        exam = Exam.objects.get(id=exam_id)
                        if question not in exam.questions.all():
                            exam.questions.add(question)
                            results["added"].append({
                                "exam_id": exam.id,
                                "exam_title": exam.title
                            })
                            logger.info(
                                "Question %s added to exam %s by user %s",
                                question.id,
                                exam.id,
                                request.user.id
                            )
                        else:
                            logger.info(
                                "Question %s already in exam %s",
                                question.id,
                                exam.id
                            )
                    except Exam.DoesNotExist:
                        results["failed_additions"].append({
                            "exam_id": exam_id,
                            "reason": "Exam not found"
                        })
            else:
                return Response(
                    {"error": "add_to_exams must be a list"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Remove from exams
        if remove_from_exams:
            if isinstance(remove_from_exams, list):
                for exam_id in remove_from_exams:
                    try:
                        exam = Exam.objects.get(id=exam_id)
                        if question in exam.questions.all():
                            exam.questions.remove(question)
                            results["removed"].append({
                                "exam_id": exam.id,
                                "exam_title": exam.title
                            })
                            logger.info(
                                "Question %s removed from exam %s by user %s",
                                question.id,
                                exam.id,
                                request.user.id
                            )
                        else:
                            logger.info(
                                "Question %s not in exam %s",
                                question.id,
                                exam.id
                            )
                    except Exam.DoesNotExist:
                        results["failed_removals"].append({
                            "exam_id": exam_id,
                            "reason": "Exam not found"
                        })
            else:
                return Response(
                    {"error": "remove_from_exams must be a list"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(results, status=status.HTTP_200_OK)