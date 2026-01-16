# `vmlc/utils` Directory

This directory serves as a collection of utility functions, helper classes, and common modules that support various functionalities across the `vmlc` application. It aims to centralize reusable logic, improve code organization, and enforce consistency.

## Key Modules and Their Responsibilities

-   **`__init__.py`**: This file aggregates and exposes key utility functions and classes from its sub-modules, making them easily importable from `vmlc.utils`.
-   **`auth.py`**: Contains helper functions related to user authentication and security.
    -   `generate_password`: Generates secure random passwords.
    -   `generate_otp`: Creates secure one-time passwords for verification.
    -   `can_resend_otp`: Implements rate-limiting logic for OTP resend requests.
    -   `send_otp_to_email`, `resend_otp_to_email`: Functions to send OTPs via email.
    -   `send_password_change_otp`, `verify_otp_for_password_change`: Specific functions for password change OTP flows.
    -   `send_welcome_email`: Sends welcome emails to newly registered users (both full and pre-registered).
-   **`dashboard.py`**: Provides logic for fetching and structuring data displayed on user dashboards.
    -   `get_candidate_dashboard_data`: Gathers comprehensive data for a candidate's dashboard (scores, exams, rankings).
    -   `get_staff_dashboard_data`: Gathers various statistics and recent activities for a staff member's dashboard.
    -   Includes helper functions for internal calculations like score stats, available/concluded exams, and leaderboard ranking.
-   **`email.py`**: Centralizes functions for building and sending various system-generated emails.
    -   `send_system_email`: Generic function to send an email using Celery tasks.
    -   `build_registration_welcome_email`: Constructs the content for welcome emails after registration.
    -   `build_pre_registration_email`: Creates email content for pre-registered users.
    -   `build_support_confirmation_email`: Generates confirmation emails for support inquiries.
    -   `build_support_notification_email`: Creates internal notification emails for new support inquiries.
    -   `create_email_html`: A utility function to generate an HTML email body from a template.
-   **`exception_handlers.py`**: Defines a custom exception handler for Django REST Framework.
    -   `custom_exception_handler`: Standardizes the format of error responses across the API, especially for validation errors.
-   **`exceptions.py`**: Contains custom exception classes specific to the VMLC application.
    -   `VMLCException`: Base class for custom API exceptions.
    -   Includes specific exceptions like `AuthenticationFailed`, `PermissionDenied`, `NotFound`, `ValidationError`, `NoRecipientsFoundError`, `InvalidMediumError`, `InvalidTokenError`, and `ServerError` for clearer error handling.
-   **`feature.py`**: Provides functionality for managing feature flags.
    -   `ToggleFeatureFlagView`: A Django REST Framework API view for toggling the state of a boolean feature flag, often used for enabling/disabling features dynamically.
-   **`functions.py`**: A module for general-purpose, reusable functions that don't fit into more specific utility categories.
    -   `generate_leaderboard_snapshot`: Orchestrates the creation and publishing of the competition leaderboard.
    -   `calculate_and_save_auto_score`: Calculates scores for candidate exam submissions.
    -   `generate_scores_snapshot`: Creates snapshots of candidate scores.
    -   `_validate_file_size`, `_validate_image_file`, `_validate_file_type`: Helpers for file validation, used in user verification processes.
    -   `validate_user_verification_files`: Validates uploaded documents for user verification.
    -   `update_staff_dashboard_cache`, `update_candidate_dashboard_cache`, `update_candidate_ranking_cache`: Functions to update and invalidate cache entries for dashboards and rankings.
-   **`helpers.py`**: Contains small, general utility functions.
    -   `sanitize_data`: Recursively redacts sensitive information from data structures, useful for safe logging.
    -   `invalidate_all_staff_dashboards`, `invalidate_all_candidate_dashboards`, `invalidate_all_candidate_records`, `invalidate_all_dashboard_caches`: Functions to clear various cache entries across the application.
-   **`query_filters.py`**: Provides functions and integration with `django-filters` for filtering querysets based on request parameters.
    -   `filter_candidates`, `filter_staffs`, `filter_users`, `filter_questions`: Functions to apply filtering logic to respective model querysets.
    -   `ExamFilter`: A `django-filters.FilterSet` for `Exam` objects.
-   **`stats.py`**: Focuses on generating statistical overviews.
    -   `generate_stats_overview_data`: Aggregates data to provide a high-level overview of candidates and staff.
    -   `_get_candidate_stats`, `_get_staff_stats`: Helper functions to retrieve specific statistics.
-   **`swagger_schemas.py`**: Defines reusable OpenAPI (Swagger) schema components.
    -   Includes schema definitions for parameters (e.g., `bearer_auth`, `api_key`, `pagination_limit`), common error responses (e.g., `error_response_400`, `error_response_401`), and request/response bodies for various API endpoints.
-   **`user.py`**: Contains utility functions related to user status and exam participation.
    -   `get_user_status_counts`: Calculates counts of users by their status (active, inactive, pending, deactivated).
    -   `get_last_concluded_exam`: Retrieves the most recently concluded exam.

## Interconnections

-   These utilities are widely used across `vmlc.views`, `vmlc.serializers`, `vmlc.tasks`, and `vmlc.signals` to perform common operations, validate data, and manage application state.
-   `auth.py` functions are integral to user registration and password recovery flows.
-   `dashboard.py` and `stats.py` rely on `vmlc.models` for data retrieval and are often triggered by `vmlc.tasks` or `vmlc.signals` for cache updates.
-   `exceptions.py` provides custom error types that are caught and handled by `exception_handlers.py`.
-   `swagger_schemas.py` is consumed by `drf-yasg` to generate interactive API documentation.

This directory is crucial for maintaining a modular, efficient, and well-structured codebase by abstracting common patterns and logic.