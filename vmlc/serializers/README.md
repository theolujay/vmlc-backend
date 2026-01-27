# `vmlc/serializers` Directory

This directory contains all the Django REST Framework serializers used within the `vmlc` application. These serializers are crucial for converting complex data types, such as Django model instances, into native Python datatypes that can be easily rendered into JSON, XML, or other content types. They also provide deserialization to validate incoming data and convert it back into Django model instances.

The serializers are organized into sub-modules based on the models or functionalities they represent.

## Key Modules and Their Responsibilities

-   **`__init__.py`**: This file acts as a central point to import and expose all serializers from its sub-modules, making them easily accessible throughout the `vmlc` application and other parts of the project.
-   **`answer.py`**: Contains serializers for `CandidateAnswer` models, used for representing and validating a candidate's submitted answers to exam questions.
    -   `CandidateAnswerSerializer`: Basic serializer for individual answers.
    -   `CandidateAnswerBulkSerializer`: Handles bulk submission of answers.
-   **`auth.py`**: Provides serializers related to authentication processes, including OTP verification and password management.
    -   `VerifyEmailOTPSerializer`: Validates OTP for email verification.
    -   `SendEmailOTPSerializer`: Handles requests to send or resend email OTPs.
    -   `RequestPasswordChangeSerializer`: Initiates password change by requesting an OTP.
    -   `PasswordChangeOTPConfirmSerializer`: Confirms the OTP for a password change request.
    -   `PasswordChangeSerializer`: Finalizes the password change with a new password and confirmed OTP.
-   **`candidate.py`**: Defines serializers for the `Candidate` model, covering different levels of detail required for various API operations.
    -   `MinimalCandidateSerializer`: A concise serializer for basic candidate information.
    -   `CandidateListSerializer`: Used for listing multiple candidates with essential details.
    -   `CandidateDetailSerializer`: Provides a comprehensive view of a single candidate, including related results and verification data.
-   **`exam_result.py`**: Contains serializers specifically designed for displaying the results of an exam, often including candidate and score details.
    -   `ExamResultSerializer`: Formats exam results for display, including candidate name and school.
-   **`exam.py`**: Houses serializers for the `Exam` model, handling exam listings, detailed views, and candidate-specific exam data.
    -   `ExamListSerializer`: Provides a summary view for multiple exams.
    -   `ExamDetailSerializer`: Offers a detailed view of a single exam, including questions and average scores.
    -   `CandidateExamSerializer`: Formats exam data specifically for candidates taking an exam, exposing only necessary question details.
-   **`leaderboard.py`**: Contains serializers for managing and displaying leaderboard snapshots.
    -   `LeaderboardSnapshotListSerializer`: Lists historical leaderboard snapshots.
    -   `PublishLeaderboardSerializer`: Validates data for publishing a new leaderboard snapshot.
    -   `CandidateLeaderboardPerfSerializer`: Serializes candidate performance data for leaderboard entries.
-   **`question.py`**: Defines serializers for the `Question` model, used for question management and display.
    -   `QuestionListSerializer`: For listing questions with basic details.
    -   `QuestionDetailSerializer`: Provides a detailed view of a single question, including its options and related exams.
    -   `CandidateQuestionSerializer`: Formats question data for candidates taking an exam, omitting correct answers.
-   **`registration.py`**: Contains serializers for user registration flows, including standard candidate/staff registration and invitation-based registrations.
    -   `BaseRegistrationSerializer`: Abstract base for common registration logic.
    -   `CandidateRegistrationSerializer`: Handles candidate self-registration.
    -   `StaffRegistrationSerializer`: Handles staff self-registration.
    -   `StaffInviteSerializer`: For inviting new staff members.
    -   `CandidateInviteSerializer`: For inviting new candidates.
-   **`role.py`**: Provides serializers for updating the roles of candidates and staff members.
    -   `CandidateRoleSerializer`: Validates and updates a candidate's role.
    -   `StaffRoleSerializer`: Validates and updates a staff member's role.
-   **`result.py`**: Defines serializers for `CandidateExamResult` models and for submitting results.
    -   `CandidateExamResultSerializer`: Displays detailed information about a candidate's result.
    -   `SubmitScoreSerializer`: Validates data for submitting or updating a candidate's score for an exam.
-   **`staff.py`**: Contains serializers for the `Staff` model, similar to candidate serializers but tailored for staff.
    -   `MinimalStaffSerializer`: Concise serializer for basic staff information.
    -   `StaffListSerializer`: Used for listing multiple staff members.
    -   `StaffDetailSerializer`: Provides a comprehensive view of a single staff member.
-   **`user.py`**: Defines serializers for the base `User` model and user verification processes.
    -   `UserSerializer`: Basic serializer for `User` model details.
    -   `MinimalUserSerializer`: A concise serializer for basic user information.
    -   `UserVerificationListSerializer`: Lists user verification requests for review.
    -   `UserVerificationStatusSerializer`: Provides the current verification status of a user.
    -   `UserVerificationUploadSerializer`: Handles the upload of verification documents.
    -   `UserVerificationActionSerializer`: Validates actions (approve/reject) on user verification requests.
-   **`user_profile.py`**: Offers serializers for dynamic user profile representations, combining `User` data with either `Candidate` or `Staff` profiles.
    -   `UserProfileDetailSerializer`: Dynamically serializes a user's detailed profile based on their role.
    -   `UserProfileListSerializer`: Lists users with dynamic profile type and role information.

## Interconnections

-   Serializers frequently cross-reference each other (e.g., `CandidateDetailSerializer` includes `UserSerializer`).
-   They interact closely with the `vmlc.models` module to fetch and save data.
-   Validation logic within serializers often leverages utility functions from `vmlc.utils`.
-   Used by `vmlc.views` to handle API request and response data.

This directory is critical for maintaining a clean, robust, and well-defined API surface for the VMLC backend.