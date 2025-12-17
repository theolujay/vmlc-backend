# Changelog


- **2025-12-02**:
  - **User Verification**: Added `rejection_reason` to the `POST /user/verification/action/{user_id}/` endpoint. When rejecting a user's verification, a reason for the rejection can be provided in the request body.

- **2025-11-28**:
  - **Breaking Change**: Updated the broadcast functionality to allow targeting both `staff` and `candidate` roles.
    - The `target_roles` field on the `POST /broadcasts/` endpoint has been changed from an array of strings to a JSON object.
    - The new structure is `{ "staff": ["role1", "role2"], "candidate": ["role3", "role4"] }`.
    - This allows for more flexible and targeted communication.
  - **Broadcast Logs**: The `GET /broadcasts/{id}/` endpoint response now includes a `role_type` field in the logs, which will be either `staff` or `candidate`.
- **2025-11-19**:
  - **User Verification**: 
    - The `GET /user/verification/status/` endpoint now returns a more granular, string-based status: `email_not_verified`, `verified`, `pending`, `rejected`, or `not_submitted`.
    - The response for a `pending` status now includes a `verification_data` object with more details.
    - The `POST /user/verification/action/{user_id}/` endpoint now accepts either `{"is_approved": true}` or `{"is_rejected": true}` to action a verification request.
- **2025-11-16**:
  - **Leaderboard**: Added `"participated_at"` field in Candidte

- **2025-11-12**:
  - **New Endpoint**: Added `GET /registration/` to provide public status on whether candidate and staff registrations are open.
  - **Removed Endpoint**: Removed the `GET /root/` endpoint as part of the URL refactoring.

- **2025-11-10**:
  - **User Management**: Updated `GET /user/list/` endpoint with more granular role-based access.
    - `moderator` and `admin` roles can now only view the list of candidates (`profile=candidate`).
    - `manager` and `superadmin` roles can view candidates, staff (`profile=staff`), and the generic user list.
  - **New Feature**: Added `GET /user/list/` endpoint to list all users with filtering by profile type (`staff` or `candidate`), active status, and search term. This endpoint is available to `moderator` roles and higher.
  - **Dashboard**: Added `concluded_exams` field that indicates exams that have passed, which has a sub-field `participation` indicating `missed`, `not_done`, or `done`.
  - **Profile**: Added `status` field to staff and candidate profiles, which is either `active`, `inactive`, `pending`, or `deactivated`.

- **2025-11-09**:
  - **New Feature**: Added `GET /stats/overview/` endpoint to provide an overview of user statistics.
    - The endpoint is accessible to `moderator` roles and higher.
    - The data is generated asynchronously and cached for performance.
    - If the data is not in the cache, the API returns a `202 Accepted` response.

- **2025-11-03**:
  - **Registration**:
    - Added `generate_password` boolean field to the registration endpoints (`/register/candidate/` and `/register/staff/`).
    - If `generate_password` is `true`, the `password` and `password2` fields are optional. The system will generate a secure password and email it to the user.

- **2025-11-01**:
  - **Question Management**:
    - Added `POST /questions/bulk-archive/` endpoint for bulk archiving of questions.
  - **Account Management**:
    - Updated `/account-management/{user_id}/` endpoint to handle `PATCH` operations (multipart).
    - Now contains `profile_picture` field, which also reflects across endpoint responses with `"user"` field.
  - **Exam**:
    - Now contains `status` field, carrying any of the following values:
      - `draft`, `scheduled`, `ongoing`, `concluded`, `cancelled`

- **2025-10-31**
  - **Exam**:
    - Contains new fields `level` and `stage_display`.
      - Should be used in "Upload Exam" or "Edit Exams".
      - `level` defaults to `1` if not provided.
      - Use case:
        *Leaderboard*
        - Paired with stage to give `stage_display`.
        - If two exams in the same stage have the same `level`, the latest exam's leaderboard shows up instead and overrides the other from showing up.
  - **Pagination**:
    - Now contains more information, such as `has_previous`.
    - Is better structured and puts into a new `"pagination"` field for each paginated response.
  - **API consistency**:
    - Standardized list responses to use the `results` key instead of `list` in the `GET /questions/` and `GET /exams/` endpoints.
  - **Leaderboard**
    - `POST /publish-leaderboard/`:
      - Now `POST /leaderboard/publish/` and requires no response body.
    - `GET /load-leaderboard/`:
      - Now `GET /leaderboard/`
      - Lists available leaderboards.
      - With query params (e.g. `stage=league`, `level=2`), leaderboard for specific exam is loaded.
      - Includes `exam_details`, `top_three`, and `remaining_candidates`.
      - Paginated.
    - `GET /leaderboard/<stage>/<level>/candidate/<candidate_id>/` is used to "View Details" of a specific candidate's submissions and performance on for that exam (and leaderboard).
    - Cached for 6 hours.
  - **OTP**:
    - `POST /resend-email-otp/`:
      - Now `POST /send-email-otp/` and accepts a `"resend"` field.

- **2025-10-30**
  - **User/profile data**
    - Profile object (e.g. candidate) `is_verified` field is renamed to `is_user_verified`.
    - User object (e.g. candidate.user) now contains `is_email_verified` field accros endpoints.
  - **User verification**
    - `is_verified` is now renamed to `is_approved`. E.g. Manager approves user verification: `"is_approved": true` | `"is_rejected": true`

- **2025-10-29**
  - **Leaderboard**
    - *Breaking Change:* Modified the leaderboard generation and retrieval process.
        - `POST /leaderboard/publish/`: Now requires no request body to specify which exam's leaderboard to generate and publish. The permission remains `admin` and higher.
        - `GET /load-leaderboard/`: Now fetches leaderboards based on user roles and can retrieve a specific exam's leaderboard using the `exam_id` query parameter.
            - When `exam_id` is provided, it returns the paginated list of ranked candidates for that exam.
            - When `exam_id` is not provided, it returns a paginated list of available leaderboard snapshots (metadata only).
    - **Addition:** Added `status` and `concluded_at` fields to the `Exam` responses.
  - **Exams**
    - `GET /exams/{exam_id}/` is now paginated.

- **2025-10-28**
  - The `meta` key in the response of `GET /exams/` and `GET /questions` endpoints have been renamed to `question_pool_data`.
  - Implemented automatic revocation of staff registrations.
    - If a newly registered staff member does not verify their email within 15 minutes, their account will be automatically deleted.
    - This allows the email to be used for registration again.
    - This feature does not apply to candidate registrations.
  - Questions difficulty `medium` is renamed to `moderate`.

### Fri, 24th of Oct, 2025
  - **Exam Results & Candidate Details** **Renamed `submitted_by` to `score_submitted_by`
  - **Candidate Details**: Candidate exam records to include detailed `submission` information within the `exams_taken` list.
  - **Question Management**: 
    Added `POST /questions/{question_id}/exams/` endpoint to add/remove questions from exams.

    Added `POST /questions/bulk-add-to-exams/` endpoint for bulk association of questions with exams.

### Tue, 22nd of Oct, 2025
- **Staff**: Added `POST /staff/invite/` endpoint.

### Wed, 15th of Oct, 2025
- **API**: Updated the response for `GET /questions/` to include a `meta` object with question counts by difficulty and pagination links. The question list is now under the `list` key.
- **API**: Updated the `questions` field in the response for `GET /exams/{exam_id}/` to include a `meta` object with question counts by difficulty.
- **API**: `date_created`, `date_updated`, and `date_recorded` have been renamed to `created_at`, `updated_at`, and `recorded_at` across all endpoints' responses.
- **API**: Updated the response for `GET /candidates/{candidate_id}/` to include a more detailed `records` object containing performance stats and exam history.
- **Exam**: `GET /exams/` now includes `scheduled_date` in response.
- **Validation**: Increased the `face_id` upload limit to 5MB. `id_card` and `verification_document` remaim at 2MB limit.

### Version 0.3.4
- **API Docs**: Added "Feature Walkthroughs & User Stories" section to provide better context for API usage.
- **API Docs**: Corrected permissions for several endpoints to match the codebase.
- **API Docs**: Corrected the response payload for the `GET /candidates/{candidate_id}/` endpoint.
### Version 0.3.3
- **Breaking Change**: Renamed `profile_photo` to `face_id` across all relevant endpoints and data models to better reflect its purpose in user verification.
- **API spec**: This current API spec can now also be reached at `<base_url>/docs/spec` (similar to Swagger).

### Version 0.3.2
- **Registration**: Now takes flat rather than nested structure.
- **Notifications**: WebSocket method now requires `X-Api-Key` and `Authorization` headers.

### Version 0.3.0
- **API Authentication**: All endpoints now require use header `X-Api-Key: <api-key>`, which may or may not be used alongside `Authorization: Bearer <access-token>`.
- **New role**: Added `manager` role with all `admin` permissions and some `superadmin` permissions.
- **"Me" Endpoints**: Added dedicated endpoints (`/candidates/me/`, `/staff/me/`) for authenticated users to easily retrieve their own profile details.
- **Login:** Response now includes full profile (and not user details alone).
- **RBAC**: Only `manager` and `superadmin` can view staff details.

### Version 0.2.0
- **Base URL** is now `https://api.verboheit.org/v1/`
- **Custom Exception Handling**: Introduced custom exception classes for more specific and consistent error responses.

### Version 0.1.0
- Initial API release
- Complete user management system
- Exam administration features
- Leaderboard functionality
- Role-based access control

_Last Updated: November 2025_