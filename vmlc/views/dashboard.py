# import logging

# from django.core.cache import cache

# from rest_framework import status
# from rest_framework.response import Response
# from rest_framework.views import APIView
# from drf_yasg.utils import swagger_auto_schema
# from drf_yasg import openapi

# from ..utils.swagger_schemas import (
#     api_key,
#     bearer_auth,
#     candidate_dashboard_response_schema,
#     staff_dashboard_response_schema,
#     error_response_401,
#     error_response_403,
# )
# from identity.permissions import (
#     CandidatePermissions,
#     ActiveModeratorPermissions,
# )
# from ..tasks import (
#     update_staff_dashboard_cache_task,
# )
# from ..utils.dashboard import get_candidate_dashboard_data

# logger = logging.getLogger(__name__)


# class CandidateDashboardView(APIView):
#     """
#     Retrieve dashboard data for the currently authenticated candidate.
#     """

#     permission_classes = CandidatePermissions

#     @swagger_auto_schema(
#         operation_summary="Get Candidate Dashboard",
#         operation_description="Retrieve dashboard data for the currently authenticated candidate.",
#         responses={
#             200: candidate_dashboard_response_schema,
#             202: openapi.Response(
#                 "Dashboard data is being generated. Please check back in a few moments."
#             ),
#             401: error_response_401,
#             403: error_response_403,
#         },
#         tags=["Dashboard"],
#         manual_parameters=[api_key, bearer_auth],
#     )
#     def get(self, request):
#         """
#         Returns candidate-specific dashboard stats and profile data.
#         """
#         candidate = request.user.candidate_profile
#         logger.warning(
#             f"CandidateDashboardView (DEPRECATED): request from user {request.user.id} (candidate_id: {candidate.pk}). "
#             "Please use the competition candidate dashboard instead."
#         )
#         cache_key = f"candidate_dashboard_{candidate.pk}"
#         cached_data = cache.get(cache_key)

#         if cached_data:
#             logger.info(f"Dashboard data for candidate {candidate.pk} found in cache.")
#             return Response(cached_data)

#         logger.info(
#             f"Dashboard data for candidate {candidate.pk} not found in cache. Generating synchronously (DEPRECATED)."
#         )
#         dashboard_data = get_candidate_dashboard_data(candidate)

#         return Response(dashboard_data)


# class StaffDashboardView(APIView):
#     """
#     Retrieve dashboard data for the currently authenticated staff member.
#     """

#     permission_classes = ActiveModeratorPermissions

#     @swagger_auto_schema(
#         operation_summary="Get Staff Dashboard",
#         operation_description="Retrieve dashboard data for the currently authenticated staff member.",
#         responses={
#             200: staff_dashboard_response_schema,
#             202: openapi.Response(
#                 "Dashboard data is being generated. Please check back in a few moments."
#             ),
#             401: error_response_401,
#             403: error_response_403,
#         },
#         tags=["Dashboard"],
#         manual_parameters=[api_key, bearer_auth],
#     )
#     def get(self, request):
#         """
#         Returns staff-specific dashboard metrics and profile data from cache if available.
#         """
#         staff = request.user.staff_profile
#         logger.info(
#             f"StaffDashboardView: request from user {request.user.id} (staff_id: {staff.pk})"
#         )
#         cached_data = cache.get(f"staff_dashboard_data_{staff.pk}")

#         if cached_data:
#             logger.info(f"Dashboard data for staff {staff.pk} found in cache.")
#             return Response(cached_data)

#         logger.info(
#             f"Dashboard data for staff {staff.pk} not found in cache. Triggering background update."
#         )
#         # If not in cache, trigger a background update
#         update_staff_dashboard_cache_task.delay(staff.pk)

#         return Response(
#             {
#                 "message": "Dashboard data is being generated. Please check back in a few moments."
#             },
#             status=status.HTTP_202_ACCEPTED,
#         )
