"""
Reusable components for drf_yasg Swagger documentation.
"""

from drf_yasg import openapi

bearer_auth = openapi.Parameter(
    "Authorization",
    openapi.IN_HEADER,
    description="Bearer token for authentication (format: 'Bearer <token>')",
    type=openapi.TYPE_STRING,
    required=True,
)

api_key = openapi.Parameter(
    "X-API-Key",
    openapi.IN_HEADER,
    description="API key for authentication.",
    type=openapi.TYPE_STRING,
    required=True,
)

pagination_limit = openapi.Parameter(
    "limit",
    openapi.IN_QUERY,
    description="Number of results to return per page.",
    type=openapi.TYPE_INTEGER,
    default=20,
)

pagination_offset = openapi.Parameter(
    "offset",
    openapi.IN_QUERY,
    description="The initial index from which to return the results.",
    type=openapi.TYPE_INTEGER,
    default=0,
)
error_response_400 = openapi.Response(
    description="Bad Request - Invalid data provided.",
    schema=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "field_name": openapi.Schema(
                type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_STRING)
            )
        },
        example={"email": ["Enter a valid email address."]},
    ),
)

error_response_401 = openapi.Response(
    description="Unauthorized - Authentication credentials were not provided or are invalid.",
    schema=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={"detail": openapi.Schema(type=openapi.TYPE_STRING)},
        example={"detail": "Authentication credentials were not provided."},
    ),
)

error_response_403 = openapi.Response(
    description="Forbidden - You do not have permission to perform this action.",
    schema=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={"detail": openapi.Schema(type=openapi.TYPE_STRING)},
        example={"detail": "You do not have permission to perform this action."},
    ),
)

error_response_404 = openapi.Response(
    description="Not Found - The requested resource could not be found.",
    schema=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={"detail": openapi.Schema(type=openapi.TYPE_STRING)},
        example={"detail": "Not found."},
    ),
)

error_response_500 = openapi.Response(
    description="Internal Server Error - An unexpected error occurred.",
    schema=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={"detail": openapi.Schema(type=openapi.TYPE_STRING)},
        example={"detail": "A server error occurred."},
    ),
)

login_request_body = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    required=["email", "password"],
    properties={
        "email": openapi.Schema(
            type=openapi.TYPE_STRING,
            format=openapi.FORMAT_EMAIL,
            example="user@example.com",
        ),
        "password": openapi.Schema(
            type=openapi.TYPE_STRING,
            format=openapi.FORMAT_PASSWORD,
            example="strongpassword123",
        ),
    },
)

login_response_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "access": openapi.Schema(type=openapi.TYPE_STRING, description="Access token"),
        "refresh": openapi.Schema(
            type=openapi.TYPE_STRING, description="Refresh token"
        ),
        "user": openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "id": openapi.Schema(
                    type=openapi.TYPE_STRING, format=openapi.FORMAT_UUID
                ),
                "email": openapi.Schema(
                    type=openapi.TYPE_STRING, format=openapi.FORMAT_EMAIL
                ),
                "first_name": openapi.Schema(type=openapi.TYPE_STRING),
                "last_name": openapi.Schema(type=openapi.TYPE_STRING),
            },
        ),
    },
)

logout_request_body = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    required=["refresh_token"],
    properties={
        "refresh_token": openapi.Schema(
            type=openapi.TYPE_STRING, description="The refresh token to blacklist."
        ),
    },
)

verify_email_otp_request_body = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    required=["email", "otp"],
    properties={
        "email": openapi.Schema(
            type=openapi.TYPE_STRING,
            format=openapi.FORMAT_EMAIL,
            example="user@example.com",
        ),
        "otp": openapi.Schema(type=openapi.TYPE_STRING, example="123456"),
    },
)

resend_email_otp_request_body = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    required=["email"],
    properties={
        "email": openapi.Schema(
            type=openapi.TYPE_STRING,
            format=openapi.FORMAT_EMAIL,
            example="user@example.com",
        ),
    },
)

request_password_change_request_body = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    required=["email"],
    properties={
        "email": openapi.Schema(
            type=openapi.TYPE_STRING,
            format=openapi.FORMAT_EMAIL,
            example="user@example.com",
        ),
    },
)

password_change_otp_confirm_request_body = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    required=["email", "otp"],
    properties={
        "email": openapi.Schema(
            type=openapi.TYPE_STRING,
            format=openapi.FORMAT_EMAIL,
            example="user@example.com",
        ),
        "otp": openapi.Schema(type=openapi.TYPE_STRING, example="123456"),
    },
)

password_change_request_body = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    required=["email", "otp", "new_password", "confirm_password"],
    properties={
        "email": openapi.Schema(
            type=openapi.TYPE_STRING,
            format=openapi.FORMAT_EMAIL,
            example="user@example.com",
        ),
        "otp": openapi.Schema(type=openapi.TYPE_STRING, example="123456"),
        "new_password": openapi.Schema(
            type=openapi.TYPE_STRING,
            format=openapi.FORMAT_PASSWORD,
            example="newstrongpassword123",
        ),
        "confirm_password": openapi.Schema(
            type=openapi.TYPE_STRING,
            format=openapi.FORMAT_PASSWORD,
            example="newstrongpassword123",
        ),
    },
)

resend_password_change_otp_request_body = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    required=["email"],
    properties={
        "email": openapi.Schema(
            type=openapi.TYPE_STRING,
            format=openapi.FORMAT_EMAIL,
            example="user@example.com",
        ),
    },
)

candidate_dashboard_response_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={"message": openapi.Schema(type=openapi.TYPE_STRING)},
)

staff_dashboard_response_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={"message": openapi.Schema(type=openapi.TYPE_STRING)},
)

account_management_response_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={"profile": openapi.Schema(type=openapi.TYPE_OBJECT)},
)

account_management_request_body = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "user": openapi.Schema(type=openapi.TYPE_OBJECT),
        "profile": openapi.Schema(type=openapi.TYPE_OBJECT),
    },
)

user_verification_status_response_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "status": openapi.Schema(type=openapi.TYPE_STRING),
        "detail": openapi.Schema(type=openapi.TYPE_STRING),
    },
)

user_verification_list_response_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "results": openapi.Schema(
            type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_OBJECT)
        )
    },
)

user_verification_action_request_body = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "is_approved": openapi.Schema(type=openapi.TYPE_BOOLEAN),
        "is_rejected": openapi.Schema(type=openapi.TYPE_BOOLEAN),
    },
)

submit_answers_request_body = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "answers": openapi.Schema(
            type=openapi.TYPE_ARRAY,
            items=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "question": openapi.Schema(type=openapi.TYPE_INTEGER),
                    "selected_option": openapi.Schema(type=openapi.TYPE_STRING),
                },
            ),
        )
    },
)

candidate_me_response_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "user": openapi.Schema(type=openapi.TYPE_OBJECT),
        "school_name": openapi.Schema(type=openapi.TYPE_STRING),
        "role": openapi.Schema(type=openapi.TYPE_STRING),
    },
)

candidate_invite_response_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={"message": openapi.Schema(type=openapi.TYPE_STRING)},
)

staff_invite_response_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={"message": openapi.Schema(type=openapi.TYPE_STRING)},
)

candidate_list_response_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "results": openapi.Schema(
            type=openapi.TYPE_ARRAY,
            items=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "user": openapi.Schema(type=openapi.TYPE_OBJECT),
                    "school_name": openapi.Schema(type=openapi.TYPE_STRING),
                    "role": openapi.Schema(type=openapi.TYPE_STRING),
                    "is_user_verified": openapi.Schema(type=openapi.TYPE_BOOLEAN),
                },
            ),
        )
    },
)

candidate_detail_response_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "user": openapi.Schema(type=openapi.TYPE_OBJECT),
        "school_name": openapi.Schema(type=openapi.TYPE_STRING),
        "face_id": openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_URI),
        "role": openapi.Schema(type=openapi.TYPE_STRING),
        "is_active": openapi.Schema(type=openapi.TYPE_BOOLEAN),
        "is_user_verified": openapi.Schema(type=openapi.TYPE_BOOLEAN),
        "id_card": openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_URI),
        "verification_document": openapi.Schema(
            type=openapi.TYPE_STRING, format=openapi.FORMAT_URI
        ),
        "created_at": openapi.Schema(
            type=openapi.TYPE_STRING, format=openapi.FORMAT_DATETIME
        ),
        "updated_at": openapi.Schema(
            type=openapi.TYPE_STRING, format=openapi.FORMAT_DATETIME
        ),
        "scores": openapi.Schema(type=openapi.TYPE_OBJECT),
    },
)

candidate_role_request_body = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "role": openapi.Schema(type=openapi.TYPE_STRING),
    },
)

exam_list_response_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "results": openapi.Schema(
            type=openapi.TYPE_ARRAY,
            items=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "id": openapi.Schema(
                        type=openapi.TYPE_STRING, format=openapi.FORMAT_UUID
                    ),
                    "title": openapi.Schema(type=openapi.TYPE_STRING),
                    "stage": openapi.Schema(type=openapi.TYPE_STRING),
                    "question_count": openapi.Schema(type=openapi.TYPE_INTEGER),
                    "created_at": openapi.Schema(
                        type=openapi.TYPE_STRING, format=openapi.FORMAT_DATETIME
                    ),
                },
            ),
        )
    },
)

exam_detail_request_body = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "title": openapi.Schema(type=openapi.TYPE_STRING),
        "stage": openapi.Schema(type=openapi.TYPE_STRING),
        "description": openapi.Schema(type=openapi.TYPE_STRING),
        "scheduled_date": openapi.Schema(
            type=openapi.TYPE_STRING, format=openapi.FORMAT_DATETIME
        ),
        "countdown_minutes": openapi.Schema(type=openapi.TYPE_INTEGER),
        "open_duration_hours": openapi.Schema(type=openapi.TYPE_INTEGER),
        "is_active": openapi.Schema(type=openapi.TYPE_BOOLEAN),
        "questions": openapi.Schema(
            type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_INTEGER)
        ),
    },
)

exam_detail_response_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "id": openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_UUID),
        "title": openapi.Schema(type=openapi.TYPE_STRING),
        "stage": openapi.Schema(type=openapi.TYPE_STRING),
        "description": openapi.Schema(type=openapi.TYPE_STRING),
        "scheduled_date": openapi.Schema(
            type=openapi.TYPE_STRING, format=openapi.FORMAT_DATETIME
        ),
        "countdown_minutes": openapi.Schema(type=openapi.TYPE_INTEGER),
        "open_duration_hours": openapi.Schema(type=openapi.TYPE_INTEGER),
        "is_active": openapi.Schema(type=openapi.TYPE_BOOLEAN),
        "questions": openapi.Schema(
            type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_INTEGER)
        ),
        "created_by": openapi.Schema(type=openapi.TYPE_OBJECT),
        "updated_by": openapi.Schema(type=openapi.TYPE_OBJECT),
        "average_score": openapi.Schema(
            type=openapi.TYPE_NUMBER, format=openapi.FORMAT_FLOAT
        ),
        "created_at": openapi.Schema(
            type=openapi.TYPE_STRING, format=openapi.FORMAT_DATETIME
        ),
    },
)

exam_result_response_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "results": openapi.Schema(
            type=openapi.TYPE_ARRAY,
            items=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "candidate_name": openapi.Schema(type=openapi.TYPE_STRING),
                    "candidate_school_name": openapi.Schema(type=openapi.TYPE_STRING),
                    "score": openapi.Schema(
                        type=openapi.TYPE_NUMBER, format=openapi.FORMAT_DECIMAL
                    ),
                    "recorded_at": openapi.Schema(
                        type=openapi.TYPE_STRING, format=openapi.FORMAT_DATETIME
                    ),
                },
            ),
        )
    },
)

question_detail_list_response_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "results": openapi.Schema(
            type=openapi.TYPE_ARRAY,
            items=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "id": openapi.Schema(type=openapi.TYPE_INTEGER),
                    "text": openapi.Schema(type=openapi.TYPE_STRING),
                    "option_a": openapi.Schema(type=openapi.TYPE_STRING),
                    "option_b": openapi.Schema(type=openapi.TYPE_STRING),
                    "option_c": openapi.Schema(type=openapi.TYPE_STRING),
                    "option_d": openapi.Schema(type=openapi.TYPE_STRING),
                    "correct_answer": openapi.Schema(type=openapi.TYPE_STRING),
                    "difficulty": openapi.Schema(type=openapi.TYPE_STRING),
                    "created_at": openapi.Schema(
                        type=openapi.TYPE_STRING, format=openapi.FORMAT_DATETIME
                    ),
                    "created_by": openapi.Schema(type=openapi.TYPE_OBJECT),
                },
            ),
        )
    },
)

candidate_exam_score_list_response_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "results": openapi.Schema(
            type=openapi.TYPE_ARRAY,
            items=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "exam": openapi.Schema(type=openapi.TYPE_STRING),
                    "score": openapi.Schema(
                        type=openapi.TYPE_NUMBER, format=openapi.FORMAT_DECIMAL
                    ),
                },
            ),
        )
    },
)

candidate_exam_response_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "id": openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_UUID),
        "title": openapi.Schema(type=openapi.TYPE_STRING),
        "stage": openapi.Schema(type=openapi.TYPE_STRING),
        "description": openapi.Schema(type=openapi.TYPE_STRING),
        "open_duration_hours": openapi.Schema(type=openapi.TYPE_INTEGER),
        "scheduled_date": openapi.Schema(
            type=openapi.TYPE_STRING, format=openapi.FORMAT_DATETIME
        ),
        "countdown_minutes": openapi.Schema(type=openapi.TYPE_INTEGER),
        "questions": openapi.Schema(
            type=openapi.TYPE_ARRAY,
            items=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "id": openapi.Schema(type=openapi.TYPE_INTEGER),
                    "text": openapi.Schema(type=openapi.TYPE_STRING),
                    "option_a": openapi.Schema(type=openapi.TYPE_STRING),
                    "option_b": openapi.Schema(type=openapi.TYPE_STRING),
                    "option_c": openapi.Schema(type=openapi.TYPE_STRING),
                    "option_d": openapi.Schema(type=openapi.TYPE_STRING),
                },
            ),
        ),
    },
)

leaderboard_snapshot_response_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={"data": openapi.Schema(type=openapi.TYPE_OBJECT)},
)

question_list_response_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "results": openapi.Schema(
            type=openapi.TYPE_ARRAY,
            items=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "id": openapi.Schema(type=openapi.TYPE_INTEGER),
                    "text": openapi.Schema(type=openapi.TYPE_STRING),
                    "difficulty": openapi.Schema(type=openapi.TYPE_STRING),
                    "created_at": openapi.Schema(
                        type=openapi.TYPE_STRING, format=openapi.FORMAT_DATETIME
                    ),
                },
            ),
        )
    },
)

question_detail_request_body = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "text": openapi.Schema(type=openapi.TYPE_STRING),
        "option_a": openapi.Schema(type=openapi.TYPE_STRING),
        "option_b": openapi.Schema(type=openapi.TYPE_STRING),
        "option_c": openapi.Schema(type=openapi.TYPE_STRING),
        "option_d": openapi.Schema(type=openapi.TYPE_STRING),
        "correct_answer": openapi.Schema(type=openapi.TYPE_STRING),
        "difficulty": openapi.Schema(type=openapi.TYPE_STRING),
    },
)

question_detail_response_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "id": openapi.Schema(type=openapi.TYPE_INTEGER),
        "text": openapi.Schema(type=openapi.TYPE_STRING),
        "option_a": openapi.Schema(type=openapi.TYPE_STRING),
        "option_b": openapi.Schema(type=openapi.TYPE_STRING),
        "option_c": openapi.Schema(type=openapi.TYPE_STRING),
        "option_d": openapi.Schema(type=openapi.TYPE_STRING),
        "correct_answer": openapi.Schema(type=openapi.TYPE_STRING),
        "difficulty": openapi.Schema(type=openapi.TYPE_STRING),
        "created_at": openapi.Schema(
            type=openapi.TYPE_STRING, format=openapi.FORMAT_DATETIME
        ),
        "created_by": openapi.Schema(type=openapi.TYPE_OBJECT),
    },
)

candidate_registration_request_body = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "email": openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_EMAIL),
        "first_name": openapi.Schema(type=openapi.TYPE_STRING),
        "last_name": openapi.Schema(type=openapi.TYPE_STRING),
        "phone": openapi.Schema(type=openapi.TYPE_STRING),
        "password": openapi.Schema(
            type=openapi.TYPE_STRING, format=openapi.FORMAT_PASSWORD
        ),
        "password2": openapi.Schema(
            type=openapi.TYPE_STRING, format=openapi.FORMAT_PASSWORD
        ),
        "school_name": openapi.Schema(type=openapi.TYPE_STRING),
    },
)

staff_registration_request_body = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "email": openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_EMAIL),
        "first_name": openapi.Schema(type=openapi.TYPE_STRING),
        "last_name": openapi.Schema(type=openapi.TYPE_STRING),
        "phone": openapi.Schema(type=openapi.TYPE_STRING),
        "password": openapi.Schema(
            type=openapi.TYPE_STRING, format=openapi.FORMAT_PASSWORD
        ),
        "password2": openapi.Schema(
            type=openapi.TYPE_STRING, format=openapi.FORMAT_PASSWORD
        ),
        "occupation": openapi.Schema(type=openapi.TYPE_STRING),
    },
)

candidate_score_list_response_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "results": openapi.Schema(
            type=openapi.TYPE_ARRAY,
            items=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "id": openapi.Schema(type=openapi.TYPE_INTEGER),
                    "candidate": openapi.Schema(type=openapi.TYPE_OBJECT),
                    "exam": openapi.Schema(type=openapi.TYPE_OBJECT),
                    "score": openapi.Schema(
                        type=openapi.TYPE_NUMBER, format=openapi.FORMAT_DECIMAL
                    ),
                    "recorded_at": openapi.Schema(
                        type=openapi.TYPE_STRING, format=openapi.FORMAT_DATETIME
                    ),
                },
            ),
        )
    },
)

submit_score_request_body = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "candidate_id": openapi.Schema(
            type=openapi.TYPE_STRING, format=openapi.FORMAT_UUID
        ),
        "score": openapi.Schema(
            type=openapi.TYPE_NUMBER, format=openapi.FORMAT_DECIMAL
        ),
    },
)

staff_me_response_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "user": openapi.Schema(type=openapi.TYPE_OBJECT),
        "occupation": openapi.Schema(type=openapi.TYPE_STRING),
        "role": openapi.Schema(type=openapi.TYPE_STRING),
    },
)

staff_list_response_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "results": openapi.Schema(
            type=openapi.TYPE_ARRAY,
            items=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "user": openapi.Schema(type=openapi.TYPE_OBJECT),
                    "role": openapi.Schema(type=openapi.TYPE_STRING),
                    "occupation": openapi.Schema(type=openapi.TYPE_STRING),
                },
            ),
        )
    },
)

staff_detail_response_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "user": openapi.Schema(type=openapi.TYPE_OBJECT),
        "occupation": openapi.Schema(type=openapi.TYPE_STRING),
        "face_id": openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_URI),
        "role": openapi.Schema(type=openapi.TYPE_STRING),
        "is_active": openapi.Schema(type=openapi.TYPE_BOOLEAN),
        "is_user_verified": openapi.Schema(type=openapi.TYPE_BOOLEAN),
        "id_card": openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_URI),
        "verification_document": openapi.Schema(
            type=openapi.TYPE_STRING, format=openapi.FORMAT_URI
        ),
        "created_at": openapi.Schema(
            type=openapi.TYPE_STRING, format=openapi.FORMAT_DATETIME
        ),
        "updated_at": openapi.Schema(
            type=openapi.TYPE_STRING, format=openapi.FORMAT_DATETIME
        ),
    },
)

staff_role_request_body = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "role": openapi.Schema(type=openapi.TYPE_STRING),
    },
)

token_refresh_request_body = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    required=["refresh"],
    properties={
        "refresh": openapi.Schema(
            type=openapi.TYPE_STRING,
            description="The refresh token to get a new access token.",
        ),
    },
)

token_refresh_response_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "access": openapi.Schema(
            type=openapi.TYPE_STRING, description="New access token"
        ),
    },
)

broadcast_list_response_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "results": openapi.Schema(
            type=openapi.TYPE_ARRAY,
            items=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "id": openapi.Schema(type=openapi.TYPE_INTEGER),
                    "subject": openapi.Schema(type=openapi.TYPE_STRING),
                    "message": openapi.Schema(type=openapi.TYPE_STRING),
                    "created_by": openapi.Schema(type=openapi.TYPE_OBJECT),
                    "created_at": openapi.Schema(
                        type=openapi.TYPE_STRING, format=openapi.FORMAT_DATETIME
                    ),
                    "mediums": openapi.Schema(
                        type=openapi.TYPE_ARRAY,
                        items=openapi.Schema(type=openapi.TYPE_STRING),
                    ),
                    "target_roles": openapi.Schema(
                        type=openapi.TYPE_ARRAY,
                        items=openapi.Schema(type=openapi.TYPE_STRING),
                    ),
                },
            ),
        )
    },
)

broadcast_detail_request_body = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "subject": openapi.Schema(type=openapi.TYPE_STRING),
        "message": openapi.Schema(type=openapi.TYPE_STRING),
        "mediums": openapi.Schema(
            type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_STRING)
        ),
        "target_roles": openapi.Schema(
            type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_STRING)
        ),
    },
)

broadcast_detail_response_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "id": openapi.Schema(type=openapi.TYPE_INTEGER),
        "subject": openapi.Schema(type=openapi.TYPE_STRING),
        "message": openapi.Schema(type=openapi.TYPE_STRING),
        "created_by": openapi.Schema(type=openapi.TYPE_OBJECT),
        "created_at": openapi.Schema(
            type=openapi.TYPE_STRING, format=openapi.FORMAT_DATETIME
        ),
        "mediums": openapi.Schema(
            type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_STRING)
        ),
        "target_roles": openapi.Schema(
            type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_STRING)
        ),
        "status": openapi.Schema(type=openapi.TYPE_STRING),
        "last_attempt": openapi.Schema(
            type=openapi.TYPE_STRING, format=openapi.FORMAT_DATETIME
        ),
        "logs": openapi.Schema(
            type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_OBJECT)
        ),
    },
)

candidate_registration_request_body = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "email": openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_EMAIL),
        "first_name": openapi.Schema(type=openapi.TYPE_STRING),
        "last_name": openapi.Schema(type=openapi.TYPE_STRING),
        "phone": openapi.Schema(type=openapi.TYPE_STRING),
        "password": openapi.Schema(
            type=openapi.TYPE_STRING, format=openapi.FORMAT_PASSWORD
        ),
        "password2": openapi.Schema(
            type=openapi.TYPE_STRING, format=openapi.FORMAT_PASSWORD
        ),
        "school_name": openapi.Schema(type=openapi.TYPE_STRING),
    },
)
