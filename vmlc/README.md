# `vmlc` Application

The `vmlc` Django application serves as the core backend for the Verboheit Mathematics League Competition. It encompasses user management (candidates, staff), exam administration, question management, scoring, leaderboard generation, real-time verification, and various utility functions to support the platform's operations.

## Key Modules and Their Responsibilities

-   **`admin.py`**: Configures the Django Admin interface for all major models within the application. It provides extensive customization for managing users, candidates, staff, exams, questions, results, and verification requests, including custom actions for email notifications and role changes, along with robust cache invalidation logic.
-   **`apps.py`**: Django application configuration for `vmlc`, ensuring signals are registered upon app readiness.
-   **`management/commands/`**:
    -   **`fix_candidate_roles.py`**: A custom Django management command to standardize candidate roles, ensuring consistency with predefined choices (e.g., converting roles to lowercase).
    -   **`populate_db.py`**: A management command designed for development and testing environments, populating the database with synthetic data for users, exams, questions, and results.
-   **`migrations/`**: Contains database migration files, managing schema changes and data transformations across different versions of the application.
-   **`models.py`**: Defines the fundamental database models that structure the entire application. This includes:
    -   **`User`**: Custom user model extending Django's `AbstractUser`, managing authentication and core user data.
    -   **`UserVerification`**: Handles the verification process for users, including document uploads (face ID, ID card, general verification document) and status tracking.
    -   **`EmailOTP`**: Stores One-Time Passwords for email verification and password reset flows.
    -   **`Staff`**: Represents administrative users with various roles (e.g., Superadmin, Manager, Admin, Moderator, Volunteer), managing different aspects of the competition.
    -   **`Question`**: Defines the structure of exam questions, including text, options, correct answer, difficulty, and creation/modification metadata.
    -   **`Exam`**: Represents a competition exam, linking questions, specifying stage (Screening, League), scheduling details, and active status.
    -   **`Candidate`**: Represents a participant in the competition, linked to a User, with roles (Screening, League, Final, Winner), and tracking school information.
    -   **`CandidateExamResult`**: Records a candidate's result for a specific exam.
    -   **`CandidateAnswer`**: Stores a candidate's submitted answer to a particular question within an exam.
    -   **`LeaderboardSnapshot`**: Captures historical states of the competition leaderboard.
    -   **`CandidateExamResultSnapshot`**: Stores historical snapshots of candidate results.
    -   **`FeatureFlag`**: Manages application-wide feature toggles, allowing dynamic enabling/disabling of functionalities.
    -   **`SupportInquiry`**: Stores details of support requests submitted by users.
    -   **`PreRegUser`**: Holds data for users who have expressed pre-registration interest.
    It also includes custom model managers, validation functions for file uploads, and various utility properties.
-   **`pagination.py`**: Provides `StandardResultsSetPagination` for consistent and customizable pagination across API list responses.
-   **`permissions.py`**: Implements custom Django REST Framework permission classes to enforce access control based on user authentication status, user type (Candidate/Staff), staff roles (hierarchical), and object ownership. Includes `HasXAPIKey` for API key authentication.
-   **`routing.py`**: (Currently empty) Placeholder for potential WebSocket routing specific to the `vmlc` app, although general WebSockets are handled by the `comms` app.
-   **`serializers/`**: A package containing numerous Django REST Framework serializers, organized by model and functionality, for data validation, conversion, and API representation. Key sub-modules include `answer`, `auth`, `candidate`, `exam`, `exam_result`, `leaderboard`, `question`, `registration`, `role`, `result`, `staff`, `user`, and `user_profile`.
-   **`signals.py`**: Connects Django signals to various models (`User`, `Candidate`, `Staff`, `Exam`, `Question`, `CandidateExamResult`, `UserVerification`) to trigger actions like cache invalidation, asynchronous task execution (e.g., for dashboard updates, stats generation), and user login processing.
-   **`storage_backends.py`**: Custom storage solutions (`PublicMediaStorage`, `PrivateMediaStorage`) that abstract file storage to either Amazon S3 (for production) or the local filesystem (for development), providing secure handling for sensitive documents and public access for others.
-   **`tasks.py`**: Contains Celery tasks for asynchronous background processing, such as calculating exam results (`compute_candidate_result_task`), generating leaderboard/result snapshots, validating user-uploaded documents (`validate_user_verification_files_task`), updating dashboard caches, and managing feature flags (`disable_expired_feature_flags_task`). Email and notification tasks (`send_mail_task`, `send_welcome_mail_task`, `send_system_email_task`) are located in the `comms` app.
-   **`templates/admin/`**: Custom Django admin templates used for enhanced functionality, such as bulk email sending and role changes for users.
-   **`tests/`**: Contains a comprehensive suite of unit and integration tests covering API endpoints, model logic, permissions, serializers, and utility functions to ensure application reliability and correctness.
-   **`urls.py`**: Defines the URL routing for all `v1` API endpoints, covering authentication, user registration, profile management, exam and question CRUD operations, score submissions, leaderboard views, and dashboard access.
-   **`utils/`**: A utility package providing helper functions and classes for various cross-cutting concerns:
    -   **`auth.py`**: Functions for generating secure passwords and OTPs, handling OTP resends, and sending welcome/password reset emails.
    -   **`dashboard.py`**: Logic for aggregating and structuring data presented on candidate and staff dashboards.
    -   **`email.py`**: Functions for dynamically building and sending system-generated emails.
    -   **`exception_handlers.py`**: Custom handler to standardize API error responses.
    -   **`exceptions.py`**: Custom exception classes for domain-specific errors.
    -   **`feature.py`**: View for safely toggling `FeatureFlag` states.
    -   **`functions.py`**: General-purpose functions, including logic for leaderboard/result snapshot generation, automatic result computation, and file validation.
    -   **`helpers.py`**: Provides data sanitization (for logging), and cache invalidation utilities.
    -   **`query_filters.py`**: Functions and Django-Filter integration for dynamically filtering querysets across various models.
    -   **`stats.py`**: Logic for generating aggregated statistics about users.
    -   **`swagger_schemas.py`**: Reusable OpenAPI (Swagger) schema definitions for API documentation.
    -   **`user.py`**: Utilities for determining user status counts and finding concluded exams.
-   **`v2/`**: A sub-package dedicated to version 2 of the API, specifically for registration and support functionalities.
    -   **`serializers/registration.py`**: A unified serializer for handling both candidate and volunteer registration, including file uploads.
    -   **`serializers/support.py`**: Serializer for handling support inquiries.
    -   **`urls.py`**: Defines URL patterns for the `v2` API endpoints.
    -   **`views/registration.py`**: Implements the `v2` registration view.
    -   **`views/support.py`**: Implements the `v2` support inquiry view.

## Interconnections

The `vmlc` application is deeply interconnected internally and with the `comms` app. It provides core models and business logic that are consumed by its own views and serializers, as well as by the `comms` app for communication-related tasks. Asynchronous operations are managed by Celery tasks defined within `vmlc.tasks`, often triggered by Django signals in `vmlc.signals`. Data integrity and consistency are maintained through custom validation logic in models and serializers, coupled with extensive caching strategies. The hierarchical permission system ensures secure access to various API resources.