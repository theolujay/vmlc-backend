"""
Custom pagination class for consistent page size handling in API responses.
"""

from collections import OrderedDict

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardResultsSetPagination(PageNumberPagination):
    """
    Standard pagination configuration using page numbers.

    - Default page size: 20 results per page
    - Client can override using `?page_size=` query param
    - Maximum allowed page size: 100
    """

    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data):
        """
        Returns paginated response for standard API endpoints.

        Use this for simple list endpoints that just need pagination.
        """
        return Response(
            OrderedDict(
                [
                    ("results", data),
                    (
                        "pagination",
                        OrderedDict(
                            [
                                ("count", self.page.paginator.count),
                                ("page", self.page.number),
                                ("page_size", self.page.paginator.per_page),
                                ("total_pages", self.page.paginator.num_pages),
                                ("has_next", self.page.has_next()),
                                ("has_previous", self.page.has_previous()),
                                ("next", self.get_next_link()),
                                ("previous", self.get_previous_link()),
                            ]
                        ),
                    ),
                ]
            )
        )

    def get_paginated_response_data(self, data):
        """
        Returns pagination data without wrapping in Response object.

        Use this when you need to add custom fields to the response
        (like in the leaderboard view where we need top_three + paginated results).

        Example:
            paginator = StandardResultsSetPagination()
            page = paginator.paginate_queryset(items, request)
            pagination_data = paginator.get_paginated_response_data(page)

            # Now add your custom fields
            return Response({
                "custom_field": "value",
                "results": pagination_data["results"],
                "pagination": pagination_data["pagination"]
            })
        """
        return OrderedDict(
            [
                ("results", data),
                (
                    "pagination",
                    OrderedDict(
                        [
                            ("count", self.page.paginator.count),
                            ("page", self.page.number),
                            ("page_size", self.page.paginator.per_page),
                            ("total_pages", self.page.paginator.num_pages),
                            ("has_next", self.page.has_next()),
                            ("has_previous", self.page.has_previous()),
                            ("next", self.get_next_link()),
                            ("previous", self.get_previous_link()),
                        ]
                    ),
                ),
            ]
        )
