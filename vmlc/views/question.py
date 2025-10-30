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

        question_pool_data = Question.objects.aggregate(
            total_questions=Count(
                "id",
                filter=Q(is_archived=False)
            ),
            hard_questions_count=Count(
                "id",
                filter=Q(difficulty=Question.Difficulty.HARD) & Q(is_archived=False)
            ),
            moderate_questions_count=Count(
                "id",
                filter=Q(difficulty=Question.Difficulty.MODERATE) & Q(is_archived=False)
            ),
            easy_questions_count=Count(
                "id",
                filter=Q(difficulty=Question.Difficulty.EASY) & Q(is_archived=False)
            ),
        )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data["question_pool_data"] = question_pool_data
            response.data["list"] = response.data.pop("results")
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

@method_decorator(
    name="post",
    decorator=swagger_auto_schema(
        operation_summary="Bulk Add Questions to Exams",
        operation_description="Add multiple questions to one or more exams. Admin only.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['question_ids', 'exam_ids'],
            properties={
                'question_ids': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(type=openapi.TYPE_INTEGER),
                    description='List of question IDs to add',
                    example=[1, 2, 3, 4, 5]
                ),
                'exam_ids': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(type=openapi.TYPE_INTEGER),
                    description='List of exam IDs to add questions to',
                    example=[10, 11]
                ),
            }
        ),
        responses={
            200: openapi.Response(
                "Questions added to exams successfully.",
                openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'summary': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'total_operations': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'successful': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'skipped': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'failed': openapi.Schema(type=openapi.TYPE_INTEGER),
                            }
                        ),
                        'details': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'added': openapi.Schema(
                                    type=openapi.TYPE_ARRAY,
                                    items=openapi.Schema(
                                        type=openapi.TYPE_OBJECT,
                                        properties={
                                            'question_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                            'exam_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                            'exam_title': openapi.Schema(type=openapi.TYPE_STRING),
                                        }
                                    )
                                ),
                                'skipped': openapi.Schema(
                                    type=openapi.TYPE_ARRAY,
                                    items=openapi.Schema(
                                        type=openapi.TYPE_OBJECT,
                                        properties={
                                            'question_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                            'exam_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                            'exam_title': openapi.Schema(type=openapi.TYPE_STRING),
                                            'reason': openapi.Schema(type=openapi.TYPE_STRING),
                                        }
                                    )
                                ),
                                'failed_questions': openapi.Schema(
                                    type=openapi.TYPE_ARRAY,
                                    items=openapi.Schema(
                                        type=openapi.TYPE_OBJECT,
                                        properties={
                                            'question_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                            'reason': openapi.Schema(type=openapi.TYPE_STRING),
                                        }
                                    )
                                ),
                                'failed_exams': openapi.Schema(
                                    type=openapi.TYPE_ARRAY,
                                    items=openapi.Schema(
                                        type=openapi.TYPE_OBJECT,
                                        properties={
                                            'exam_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                            'reason': openapi.Schema(type=openapi.TYPE_STRING),
                                        }
                                    )
                                ),
                            }
                        )
                    }
                )
            ),
            400: error_response_400,
            401: error_response_401,
            403: error_response_403,
        },
        tags=["Questions"],
        manual_parameters=[api_key, bearer_auth],
    ),
)
class BulkQuestionExamAssociationView(APIView):
    """
    Bulk add questions to exams.
    
    POST: Add multiple questions to multiple exams in one operation.
    
    Permissions:
        - Only accessible to verified staff with role: admin or superadmin.
    """
    
    permission_classes = VerifiedAdminPermissions
    
    def post(self, request):
        """
        Add multiple questions to multiple exams.
        
        Request body:
        {
            "question_ids": [1, 2, 3, 4],
            "exam_ids": [10, 11]
        }
        """
        question_ids = request.data.get("question_ids", [])
        exam_ids = request.data.get("exam_ids", [])
        
        # Validation
        if not question_ids:
            return Response(
                {"error": "question_ids is required and cannot be empty"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not exam_ids:
            return Response(
                {"error": "exam_ids is required and cannot be empty"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not isinstance(question_ids, list):
            return Response(
                {"error": "question_ids must be a list"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not isinstance(exam_ids, list):
            return Response(
                {"error": "exam_ids must be a list"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Initialize results tracking
        results = {
            "summary": {
                "total_operations": len(question_ids) * len(exam_ids),
                "successful": 0,
                "skipped": 0,
                "failed": 0,
            },
            "details": {
                "added": [],
                "skipped": [],
                "failed_questions": [],
                "failed_exams": [],
            }
        }
        
        # Bulk fetch questions and exams (efficient!)
        questions = Question.objects.filter(
            id__in=question_ids, 
            is_archived=False
        )
        exams = Exam.objects.filter(id__in=exam_ids)
        
        # Track which IDs were found
        found_question_ids = set(questions.values_list('id', flat=True))
        found_exam_ids = set(exams.values_list('id', flat=True))
        
        # Track missing IDs
        missing_question_ids = set(question_ids) - found_question_ids
        missing_exam_ids = set(exam_ids) - found_exam_ids
        
        # Log missing questions
        if missing_question_ids:
            for q_id in missing_question_ids:
                results["details"]["failed_questions"].append({
                    "question_id": q_id,
                    "reason": "Question not found or archived"
                })
                results["summary"]["failed"] += len(exam_ids)  # Failed for all exams
            
            logger.warning(
                "Questions not found by user %s: %s",
                request.user.id,
                list(missing_question_ids)
            )
        
        # Log missing exams
        if missing_exam_ids:
            for e_id in missing_exam_ids:
                results["details"]["failed_exams"].append({
                    "exam_id": e_id,
                    "reason": "Exam not found"
                })
                results["summary"]["failed"] += len(found_question_ids)  # Failed for all questions
            
            logger.warning(
                "Exams not found by user %s: %s",
                request.user.id,
                list(missing_exam_ids)
            )
        
        # Process each exam-question combination
        for exam in exams:
            # Get existing question IDs for this exam (efficient check)
            existing_question_ids = set(
                exam.questions.filter(id__in=found_question_ids).values_list('id', flat=True)
            )
            
            for question in questions:
                try:
                    # Check if already exists
                    if question.id in existing_question_ids:
                        results["details"]["skipped"].append({
                            "question_id": question.id,
                            "exam_id": exam.id,
                            "exam_title": exam.title,
                            "reason": "Already exists"
                        })
                        results["summary"]["skipped"] += 1
                        logger.debug(
                            "Question %s already in exam %s, skipping",
                            question.id,
                            exam.id
                        )
                        continue
                    
                    # Add the question to the exam
                    exam.questions.add(question)
                    results["details"]["added"].append({
                        "question_id": question.id,
                        "exam_id": exam.id,
                        "exam_title": exam.title
                    })
                    results["summary"]["successful"] += 1
                    
                    logger.info(
                        "Question %s added to exam %s (%s) by user %s",
                        question.id,
                        exam.id,
                        exam.title,
                        request.user.id
                    )
                    
                except Exception as e:
                    results["details"]["added"].append({
                        "question_id": question.id,
                        "exam_id": exam.id,
                        "reason": str(e)
                    })
                    results["summary"]["failed"] += 1
                    
                    logger.error(
                        "Error adding question %s to exam %s: %s",
                        question.id,
                        exam.id,
                        str(e)
                    )
        
        # Summary log
        logger.info(
            "Bulk operation by user %s: %s successful, %s skipped, %s failed out of %s total",
            request.user.id,
            results["summary"]["successful"],
            results["summary"]["skipped"],
            results["summary"]["failed"],
            results["summary"]["total_operations"]
        )
        
        return Response(results, status=status.HTTP_200_OK)