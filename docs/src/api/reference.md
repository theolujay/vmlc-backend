# VMLC API Documentation

## Table of Contents

- [Overview](#overview)
- [Getting Started](#getting-started)
  - [Base URL](#base-url)
  - [Authentication](#authentication)
  - [User Roles, Permissions, and API Access](#user-roles-permissions-and-api-access)
  - [Feature Walkthroughs and User Stories](#feature-walkthroughs-and-user-stories)
  - [Endpoint Mapping](#endpoint-mapping)
- [API Endpoints](#api-endpoints)
  - [Health & Status](#health-status)
  - [Authentication](#authentication_1)
  - [Registration](#registration)
  - [Email & Password](#email-password-flows)
  - [User Profiles ("Me" Endpoints)](#user-profiles-me-endpoints)
  - [Candidate Management](#candidate-management)
  - [Staff Management](#staff-management)
  - [User Management](#user-management)
  - [User Verification](#user-verification)
  - [Account Management](#account-management)
  - [Exam Management](#exam-management)
  - [Question Management](#question-management)
  - [Scoring & Submissions](#scoring-submissions)
  - [Dashboard](#dashboard)
  - [Leaderboard](#leaderboard)
  - [Notifications](#notifications-with-websockets)
  - [Broadcast Management](#broadcast-management)
- [Advanced Topics](#advanced-topics)
  - [Query Parameters](#query-parameters)
  - [Error Handling](#error-handling)
  - [Rate Limiting](#rate-limiting)
  - [Versioning](#versioning)
- [Support](#support)
  - [Interactive Documentation](#interactive-documentation)
  - [Support](#support)
  - [Changelog](#changelog)

---

## Overview

The VMLC API provides an integrated backend service for the Verboheit Mathematics League Competition, handling registration, exam administration, scoring, and leaderboard functionality with user management and role-based access control based on the two types of users--staff and candidate

---

## Getting Started

### Base URL

`https://api.verboheit.org/v1/` ~ production
`https://staging-api.verboheit.org/v1/`~ staging

All endpoints are relative to this base URL.

---

### Authentication

The API uses `X-Api-Key` for general authentication. The API key should be provided in the `X-Api-Key` header:

`X-Api-Key: <your_api_key>`

For endpoints that require user-specific permissions, a JWT access token must also be provided in the `Authorization` header. This is typically required for actions performed by authenticated users, such as accessing their profile, taking an exam, or for staff members managing resources. Some endpoints may require both `X-Api-Key` and `Authorization: Bearer <access-token>`.

#### Login Flow

**Endpoint:** `POST /auth/login/`

**Headers:**

```text
X-Api-Key: <your_api_key>
Content-Type: application/json
```

**Request Body:**

```json
{
  "email": "your_email@example.com",
  "password": "your_password"
}
```

**Response:** `200 OK`

```json
{
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "profile": {
    "user": {
      "id": "4ecxxxxx-8f43-xxxx-xxxx-xxxxxxxxxx",
      "email": "john@example.com",
      "first_name": "John",
      "last_name": "Doe",
      "phone": "+23490xxxxxxxx",
      "date_joined": "2024-01-15T10:30:00Z"
    },
    "school": "Mathematics High School",
    "role": "screening"
  }
}
```

_Note: The `profile` field will contain either `candidate` or `staff` specific data based on the user's role._

#### Token Management

##### Refresh Token

**Endpoint:** `POST /auth/token/refresh/`

**Request Body:**

```json
{
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

**Response:** `200 OK`

```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

##### Logout

**Endpoint:** `POST /auth/logout/`

**Request Body:**

```json
{
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

**Response:** `204 No Content`

---

## Health & Status

### Health Check

The health check endpoint provides a simple way to verify the API's operational status.

**Endpoint:** `GET /health/`
**Required Role:** None (Public)

**Response:** `200 OK`

```json
{
  "status": "healthy",
  "timestamp": "2025-09-18T10:00:00.000000Z"
}
```

### Registration Status

This endpoint provides a public status check for candidate and staff registrations. It indicates whether new registrations are currently open or closed, which can be controlled by feature flags.

**Endpoint:** `GET /registration/`
**Required Role:** None (Public)

**Response:** `200 OK`

```json
{
  "is_candidate_reg_open": true,
  "is_staff_reg_open": false,
  "support_email": "verboheitmlc@gmail.com"
}
```

---

## User Roles, Permissions, and API Access

This table provides a detailed breakdown of each user role, its key abilities on the platform, and the primary API endpoints it has access to.

### Candidate User Type

| Role            | Key Abilities (What they can do)                                                                                                                                  | Accessible API Endpoints                                                                                                                                                                                                                                                                           |
| --------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **`screening`** | • View their personal dashboard.<br>• Take screening-level exams.<br>• View their own profile and verification status.<br>• View screening leaderboard snapshots. | • `GET /dashboard/candidate/`<br>• `GET /candidates/me/`<br>• `GET /user/verification/status/`<br>• `POST /user/verification/upload/`<br>• `GET /exams/{id}/take-exam/` (where `stage` is `screening`)<br>• `POST /exams/{id}/submit-exam-answers/`<br>• `GET /leaderboard/` (for screening exams) |
| **`league`**    | • All `screening` abilities.<br>• Take league-level exams.<br>• View the competition leaderboard snapshots or a specific exam leaderboard.                        | • All `screening` endpoints.<br>• `GET /leaderboard/`<br>• `GET /exams/{id}/take-exam/` (where `stage` is `league`)                                                                                                                                                                                |
| **`final`**     | • All `league` abilities.<br>• Access to (offline) final-stage exams.                                                                                             | • All `league` endpoints.<br>• `GET /exams/{id}/take-exam/` (where `stage` is `final`)                                                                                                                                                                                                             |
| **`winner`**    | • Ceremonial role with all candidate permissions. Registered winner of the final stage.                                                                           | • All `final` endpoints.                                                                                                                                                                                                                                                                           |

### Staff User Type

_(Permissions are hierarchical; higher roles inherit permissions from lower roles)_

| Role             | Key Abilities (What they can do)                                                                                                                                                                                        | Newly Accessible API Endpoints (in addition to lower roles)                                                                                                                                                                                                                                         |
| ---------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **`volunteer`**  | • View their own profile.<br>• Submit their own documents for verification.                                                                                                                                             | • `GET /staff/me/`<br>• `GET /user/verification/status/`<br>• `POST/PATCH /user/verification/upload/`                                                                                                                                                                                               |
| **`admin`**      | • View details for any candidate.<br>• Change roles for candidates.<br>• Full management (CRUD) of exams.<br>• Manually submit scores.<br>• Publish leaderboard for a specific exam.                                    | • `GET /candidates/{id}/`<br>• `GET /candidates/{id}/scores/`<br>• `GET /candidates/{id}/exam-history/`<br>• `PUT /candidates/{id}/roles/assign/`<br>• `GET/POST /exams/`<br>• `GET/PUT/PATCH/DELETE /exams/{id}/`<br>• `PUT /exams/{id}/submit-exam-score/`<br>• `POST /leaderboard/publish/`      |
| **`manager`**    | • View details for any staff member.<br>• Change roles for staff (except `manager` or `superadmin`).<br>• Manage user verifications for candidates and staff members (approve/reject).<br>• Create and view broadcasts. | • `GET /staff/{id}/`<br>• `PUT /staff/{id}/roles/assign/`<br>• `GET /user/verification/list/`<br>• `POST /user/verification/action/{id}/`<br>• `GET /user/verification/documents/{type}/{id}/`<br>• `GET/POST /broadcasts/`<br>• `GET /broadcasts/{id}/`<br>• `GET/PATCH /account-management/{id}/` |
| **`superadmin`** | • Can assign any staff role (except `superadmin`).<br>• Has full platform control inheriting all permissions.                                                                                                           | _(Inherits all `manager` endpoints with zero restrictions)_                                                                                                                                                                                                                                         |
| **`sponsor`**    | • A vanity role with no specific permissions.                                                                                                                                                                           | _(No specific endpoints)_                                                                                                                                                                                                                                                                           |

**NOTE**: Users must already have their emails verified and be user-verified to perform actions beyond `get-started`.

#### Role Progression

- **Candidates**: `screening` → `league` → `final` → `winner` (progression is managed by staff with `admin` role or higher)
- **Staff**: Roles are assigned by a `manager` or `superadmin`.

---

## Feature Walkthroughs and User Stories

This is a high-level overview of the core features and users' perspectives.

### Feature: Onboarding, Email Verification & First Login

```gherkin
Feature: Registration, Email verification, and initial redirect
  In order to use the platform correctly
  As a new user (candidate or staff)
  Flow = registration → verify → login → get-started

  Scenario: Candidate signs up, verifies email, and reaches Get Started
    Given a person navigates to the Candidate Registration page
    When they submit valid registration details
    Then the system creates the account with default role "screening"
    And the system returns "201 Created"
    And an OTP is sent to the provided email
    When they POST the correct OTP to verify email
    Then the system responds "200 OK" and marks email verified
    When the user logs in with valid credentials
    Then they are redirected to the "Get Started" page
    And the user's role remains "screening"
    And the Tour card is locked until the user is marked "user_verified"

  Scenario: Staff signs up, verifies email, and reaches Get Started
    Given a person navigates to the Staff Registration page
    When they submit valid registration details
    Then the system creates the account with default role "volunteer"
    And the system returns "201 Created"
    And an OTP is sent to the provided email
    When they POST the correct OTP to verify email
    Then the system responds "200 OK" and marks email verified
    When the user logs in with valid credentials
    Then they are redirected to the "Get Started" page
    And the Tour card remains locked until the user is promoted to at least "moderator"
```

### Feature: User Verification, Role Promotions & Tour Unlocking

```gherkin
Feature: Verification and role promotion flow
  In order to enable role-based features and the Tour card
  As verification / admin staff
  Action: move users between roles

  Scenario: Candidate submits verification documents and gets approved
    Given a logged-in candidate with email verified and role "screening"
    When they upload verification documents (face_id, id_card, verification_document)
    Then the verification status becomes "pending"
    When a manager or superadmin approves the verification
    Then the user's verification status becomes "verified"
    And the candidate remains "screening" until staff assigns "league" or higher
    And after being marked "verified" the candidate can access their candidate dashboard

  Scenario: Staff promotion that unlocks the Tour card
    Given a logged-in staff member currently role "volunteer"
    And their email is verified and they have submitted verification documents
    When a manager or superadmin assigns role "moderator" to the staff member
    Then the Tour card becomes unlocked on their Get Started page
    And moderator-level navigation (candidate lists, question management) becomes available
```

### Feature: Dashboards & Role-based Access (Acceptance criteria)

```gherkin
Feature: Dashboards and permissions
  So that each role only sees and does what it should

  Scenario: Screening candidate dashboard access
    Given a logged-in candidate with role "screening" and is_user_verified = true
    When they open their Dashboard
    Then they see: available screening exams, exam history, profile information
    And they do not see the leaderboard or league exams

  Scenario: League candidate access and leaderboard
    Given a logged-in candidate with role "league"
    When they open the Leaderboards tab
    Then they can view leaderboard results
    And they can access league-stage exams only

  Scenario: Moderator dashboard and CRUD questions
    Given a logged-in staff member with role "moderator"
    When they open the Staff Dashboard
    Then they can view list of candidates and question management (CRUD)
    And they can view the leaderboard
    And they view candidate details, change candidate roles or manage the leaderboard

  Scenario: Admin role permissions
    Given a logged-in staff member with role "admin"
    When they open the Admin Dashboard
    Then they can view list of candidates, view candidate details, manage exams and questions
    And they can assign candidate roles (screening → league → final → winner)
    And they can update the leaderboard

  Scenario: Manager permissions
    Given a logged-in staff member with role "manager"
    When they review verification queue
    Then they can approve or reject user verification requests
    And they can create broadcasts targeted at staff/candidates (per target_roles)
    And they can manage staff roles except "manager" or "superadmin"

  Scenario: Superadmin ultimate control (except superadmin creation)
    Given a logged-in staff member with role "superadmin"
    When they view any staff profile
    Then they can assign any staff role (except creating another superadmin)
```

### Endpoint mapping

> Notes applicable to most endpoints
>
> - Header: `X-Api-Key: <your_api_key>` (required for all endpoints).
> - Authenticated user endpoints also require `Authorization: Bearer <access-token>`.
> - Role requirements shown when specified.
> - Use JSON unless `multipart/form-data` is stated.

---

#### Health & discovery

- `GET /health/` — public health check. `200 OK`.

#### Interactive docs

- Swagger UI: `/docs/swagger/`
- ReDoc: `/docs/redoc/`
- Spec endpoint: `/docs/spec` (API doc).

---

#### Authentication

- `POST /auth/login/` — login. Request: `{ email, password }`. Returns `access`, `refresh`, `profile`. `200 OK`.
- `POST /auth/token/refresh/` — refresh token. `200 OK`.
- `POST /auth/logout/` — logout (body: refresh token). `204 No Content`.

---

#### Registration

- `POST /register/candidate/` — candidate signup. `201 Created`. Default role: `screening`.
- `POST /register/staff/` — staff signup. `201 Created`. Default role: `volunteer`.

---

#### Email & password flows

- `POST /verify-email-otp/` — verify registration OTP. Request: `{ email, otp }`. `200 OK`.
- `POST /send-email-otp/` — send/resend OTP. `200 OK` (returns masked email + `expires_in_minutes`).

Password-change:

- `POST /auth/password-change/request/` — request OTP to change password. `200 OK`.
- `POST /auth/password-change/confirm-otp/` — confirm OTP for password change. `200 OK`.
- `POST /auth/password-change/` — change password (otp + new_password). `200 OK`.
- `POST /auth/password-change/resend-otp/` — resend OTP for password change. `200 OK`.

---

#### "Me" profile endpoints

- `GET /candidates/me/` — authenticated candidate's profile. `200 OK`.
- `GET /staff/me/` — authenticated staff profile. `200 OK`.

---

#### Candidate management (staff-facing)

- `GET /candidates/` — list candidates. Required role: `moderator`+. Supports `page`, `search`, `role`, `school`, `verified`. `200 OK`.
- `GET /candidates/{candidate_id}/` — operation_description="Retrieve dashboard data for a specific candidate." Role: `admin`+. `200 OK`.
- `PUT /candidates/{candidate_id}/roles/assign/` — assign candidate role (e.g., `league`, `final`, `winner`). Role: `admin`+. `200 OK`.
- `GET /candidates/{candidate_id}/scores/` — get candidate scores. Role: `admin`+. `200 OK`.
- `GET /candidates/{candidate_id}/exam-history/` — full exam history. Role: `admin`+. `200 OK`.

---

#### Staff management (staff-facing)

- `GET /staff/` — list staff. Role: `moderator`+. Query filters: `page`, `search`, `role`, `occupation`. `200 OK`.
- `POST /staff/invite/` — invite a new staff member. Role: `manager` or `superadmin`. `201 Created`.
- `GET /staff/{staff_id}/` — staff details. Role: `manager` or `superadmin`. `200 OK`.
- `PUT /staff/{staff_id}/roles/assign/` — assign staff role (manager/superadmin allowed to assign except superadmin creation). Role: `manager` or `superadmin`. `200 OK`.
- `GET /account-management/{id}/` and `PATCH /account-management/{id}/` — account management endpoints used by staff (mentioned in role table). Role: `manager`+ or owner.

---

#### User management (staff-facing)

- `GET /user/list/` — list all users. Role: `moderator`+. Query filters: `profile` ('candidate' for moderator+, 'staff' for manager+), `is_active`, `search`. `200 OK`.

---

#### User verification endpoints

- `GET /user/verification/status/` — get current user's verification status. `200 OK`.
- `GET /user/verification/status/{user_id}/` — manager+ or owner view other users' status. `200 OK`.
- `POST /user/verification/upload/` — submit verification documents (multipart/form-data). Files: `face_id`, `id_card`, `verification_document`. Any authenticated user. `200 OK / 201`.
- `PATCH /user/verification/upload/` — update/resubmit verification docs. Any authenticated user. `200 OK`.
- `GET /user/verification/list/` — list verification requests (manager+). Query filters: `is_pending`, `is_approved`, `is_rejected`. `200 OK`.
- `POST /user/verification/action/{id}/` — approve/reject a verification (manager+). `200 OK`.
- `GET /user/verification/documents/{type}/{id}/` — download verification docs (manager+ or owner). `200 OK`.

---

#### Exam management

- `GET /exams/` — list exams. Role: `admin`+. Query filters: `page`, `stage`, `active`, `date_from`, `date_to`. `200 OK`.
- `POST /exams/` — create exam. Role: `admin`+. `201 Created`.
- `GET /exams/{id}/` — retrieve exam. Role: `admin`+. `200 OK`.
- `PUT /exams/{id}/`, `PATCH /exams/{id}/`, `DELETE /exams/{id}/` — update/delete exam. Role: `admin`+. `200/204`.
- `GET /exams/{id}/take-exam/` — candidate takes exam (stage-limited: screening/league/final). Candidate must be eligible. `200 OK`.
- `POST /exams/{id}/submit-exam-answers/` — candidate submits answers. `200 OK`.

---

#### Question management

- `GET /questions/` — list questions. `GET/POST /questions/` — create question (moderator+ for CRUD). `200/201 OK`.
- `GET /questions/{id}/`, `PUT /questions/{id}/`, `PATCH /questions/{id}/`, `DELETE /questions/{id}/` — CRUD single question (moderator+). `200/204`.

---

#### Dashboards

- `GET /dashboard/candidate/` — candidate dashboard (shows exams allowed, history, profile). Candidate role required. `200 OK`.
- `GET /dashboard/staff/` — staff dashboard (moderator+). `200 OK`. Contains staff info, candidate counts, exams, questions, scores. `200 OK`.

---

### Statistics

- `GET /stats/overview/` — get overall statistics for candidates and staff. Role: `moderator`+. `200 OK` (or `202 Accepted` if generating).

---

#### Scoring & Submissions

- `POST /exams/{id}/submit-exam-answers/` — candidate submits answers. `200 OK`.

- `PUT /exams/{id}/submit-exam-score/` — manual score submission (admin). `200 OK`.

---

#### Leaderboard

- `POST /leaderboard/publish/` — start generation & publish snapshot for a specific exam (admin+). `202 Accepted`.

- `GET /leaderboard/` — fetch latest published snapshot(s). Role: `league` candidates and above, all staff. Query: `exam_id` (optional, to get a specific leaderboard), `limit`, `offset`. `200 OK`.

---

</details>

### Broadcast Management

The broadcast system allows authorized staff to send targeted communications to users (candidates and/or staff). Broadcasts are sent asynchronously, and their status can be tracked.

#### List Broadcasts

**Endpoint:** `GET /broadcasts/`
**Headers:**

```text
X-Api-Key: <your_api_key>
Authorization: Bearer <access_token>
```

**Required Role:** `manager` or higher
**Response:** `200 OK`

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "subject": "Important Announcement",
      "message": "Please review the new exam schedule.",
      "created_by": {
        "user": {
          "email": "manager@example.com",
          "first_name": "Manager",
          "last_name": "User"
        }
      },
      "created_at": "2025-09-20T10:00:00Z",
      "mediums": ["email", "platform"],
      "target_roles": {
        "candidate": ["league", "final"],
        "staff": ["moderator", "volunteer"]
      }
    }
  ]
}
```

#### Create Broadcast

**Endpoint:** `POST /broadcasts/`
**Headers:**

```text
X-Api-Key: <your_api_key>
Authorization: Bearer <access_token>
```

**Required Role:** `manager` or higher
**Request Body:**

```json
{
  "subject": "New Exam Available",
  "message": "The final stage exam is now open. Good luck!",
  "mediums": ["email", "platform"],
  "target_roles": {
    "staff": ["volunteer", "moderator"],
    "candidate": ["final"]
  }
}
```

_Note: The `target_roles` object must contain either a `staff` key, a `candidate` key, or both. The values should be arrays of valid roles._

- _Valid `staff` roles: `volunteer`, `moderator`, `admin`, `manager`, `superadmin`_
- _Valid `candidate` roles: `screening`, `league`, `final`, `winner`_

**Response:** `201 Created`

```json
{
  "id": 2,
  "subject": "New Exam Available",
  "message": "The final stage exam is now open. Good luck!",
  "created_by": { "...": "..." },
  "created_at": "2025-09-21T12:00:00Z",
  "status": "pending",
  "mediums": ["email", "platform"],
  "target_roles": {
    "staff": ["volunteer", "moderator"],
    "candidate": ["final"]
  },
  "logs": []
}
```

_Note: Creating a broadcast triggers an asynchronous task. The response includes the task_id for tracking. If platform is a medium, a real-time notification will be pushed to connected clients via WebSockets._

#### Get Broadcast Details

**Endpoint:** `GET /broadcasts/{id}/`
**Headers:**

```text
X-Api-Key: <your_api_key>
Authorization: Bearer <access_token>
```

**Required Role:** `manager` or higher
**Response:** `200 OK`

```json
{
  "id": 1,
  "subject": "Important Announcement",
  "message": "Please review the new exam schedule.",
  "created_by": {
    "user": {
      "email": "manager@example.com",
      "first_name": "Manager",
      "last_name": "User"
    }
  },
  "created_at": "2025-09-20T10:00:00Z",
  "mediums": ["email", "platform"],
  "target_roles": {
    "candidate": ["league", "final"],
    "staff": ["moderator", "volunteer"]
  },
  "status": "sent",
  "last_attempt": "2025-09-20T10:00:15Z",
  "logs": [
    {
      "id": 1,
      "medium": "email",
      "target_role": "league",
      "role_type": "candidate",
      "status": "sent",
      "message": "Successfully sent to 50 recipients",
      "attempted_at": "2025-09-20T10:00:10Z"
    }
  ]
}
```

_Note: The response for this endpoint is cached for performance. The cache is invalidated when the broadcast sending task completes._

### Notifications with WebSockets

Clients receive notifications using WebSockets. For example, [broadcasts](#create-broadcast) made via the `platform` medium at target users (or roles) will come through the notifications endpoint, allowing clients to receive instant updates without needing to poll the server.

#### Real-time Notifications

Connect to this endpoint to receive `platform` notifications in real-time.

**Endpoint:** `ws://<host>/v1/ws/notifications/` (preferrably `wss://` for secure connections in production)

**Authentication:**
This endpoint requires dual authentication:

- `X-Api-Key`: In the headers, to authenticate the client application.
- `Authorization: Bearer <access_token>`: In the headers, to identify the user.

**Required Role:** Any authenticated user.

**Receiving Messages (Server-to-Client):**
When a new notification is generated for the authenticated user (e.g., via a broadcast), the server will push a JSON message with the following structure:

```json
{
  "type": "notification_activity",
  "message": {
    "id": 123,
    "subject": "New Exam Available",
    "message": "The final stage exam is now open. Good luck!",
    "read": false,
    "created_at": "2025-09-21T12:00:00.123456Z"
  }
}
```

**Sending Messages (Client-to-Server):**
Clients can send messages to the server to perform actions, like `mark_as_read`. The message must be a JSON object with an `action` and a `data` payload.

**Action: `mark_as_read`**
Marks a specific notification as read.

**Request Payload:**

```json
{
  "action": "mark_as_read",
  "data": {
    "notification_id": 123
  }
}
```

**Server Response:**
If the action is unknown or the payload is invalid, the server will send back an error message:

```json
{
  "type": "error",
  "message": "Unknown action: <action_name>"
}
```

#### Account management & misc

- `GET /account-management/{id}/`, `PATCH /account-management/{id}/` — staff/account admin endpoints (manager+).
- `POST /publish-scores/` — (commented/optional) publish scores snapshot (admin+). Triggers async task. May be present in code but commented in docs.

---

#### Rate limits / error codes

- Rate limits: Authenticated 1000/day, 60/hour, 10/min. Anonymous 60/day, 5/min. Rate-limit headers present.
- Standard error JSON: `{ "detail": "...", "code": "error_code" }`. Common error codes: `permission_denied`, `invalid_otp`, `leaderboard_hidden`, `registration_closed`, etc. Use these in negative tests.

---

## API Endpoints

### Registration

Registration endpoints allow new users to sign up as either candidates or staff members. Registration can be dynamically enabled or disabled via feature flags.

#### Register New Users

**Candidate Registration**  
**Endpoint:** `POST /register/candidate/`  
**Headers:**

```text
X-Api-Key: <your_api_key>
```

**Request Body:**

```json
{
  "email": "john@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "phone": "+23490xxxxxxxx",
  "password": "secure_password_123",
  "password2": "secure_password_123",
  "school": "Mathematics High School",
  "generate_password": true
}
```

_Note: If `generate_password` is set to `true`, the `password` and `password2` fields can be omitted. The system will generate a secure password and email it to the user._

**Response:** `201 Created`

```json
{
  "message": "Registration successful."
}
```

_Note: If candidate registration is closed, a `403 Forbidden` response will be returned. Kindly reach the developer._

**Staff Registration**  
**Endpoint:** `POST /register/staff/`  
**Headers:**

```text
X-Api-Key: <your_api_key>
```

**Request Body:**

```json
{
  "email": "jane@example.com",
  "first_name": "Jane",
  "last_name": "Smith",
  "phone": "+23490xxxxxxxx",
  "password": "secure_password_123",
  "password2": "secure_password_123",
  "occupation": "Mathematics Teacher",
  "generate_password": true
}
```

_Note: If `generate_password` is set to `true`, the `password` and `password2` fields can be omitted. The system will generate a secure password and email it to the user._

_Note: If staff registration is closed, a `403 Forbidden` response will be returned._

---

### Email & Password

#### Verify Email with OTP

**Endpoint:** `POST /verify-email-otp/`  
**Headers:**

```text
X-Api-Key: <your_api_key>
```

**Request Body:**

```json
{
  "email": "john@example.com",
  "otp": "123456"
}
```

**Response:** `200 OK`

```json
{
  "message": "Email verified successfully."
}
```

#### Send/Resend Email OTP

**Endpoint:** `POST /send-email-otp/`
**Headers:**

```text
X-Api-Key: <your_api_key>
```

**Request Body:**

```json
{
  "email": "john@example.com",
  "resend": false
}
```

_Note: Set `"resend": true` to resend a a (new) OTP._ If not resend, the field can be ommitted.

**Response:** `200 OK`

```json
{
  "message": "OTP has been sent to your email address",
  "email": "joh***@example.com",
  "expires_in_minutes": 10
}
```

#### Request Password Change OTP

**Endpoint:** `POST /auth/password-change/request/`
**Headers:**

```text
X-Api-Key: <your_api_key>
```

**Request Body:**

```json
{
  "email": "user@example.com"
}
```

**Response:** `200 OK`

```json
{
  "message": "Password change verification code sent to your email",
  "email": "use***@example.com",
  "expires_in_minutes": 10
}
```

#### Confirm OTP for Password Change

**Endpoint:** `POST /auth/password-change/confirm-otp/`
**Headers:**

```text
X-Api-Key: <your_api_key>
```

**Request Body:**

```json
{
  "email": "user@example.com",
  "otp": "123456"
}
```

**Response:** `200 OK`

```json
{
  "message": "OTP verified. User confirmed for password change. Proceed to change password."
}
```

#### Change Password

**Endpoint:** `POST /auth/password-change/`
**Headers:**

```text
X-Api-Key: <your_api_key>
```

**Request Body:**

```json
{
  "email": "user@example.com",
  "otp": "123456",
  "new_password": "your_new_secure_password",
  "confirm_password": "your_new_secure_password"
}
```

**Response:** `200 OK`

```json
{
  "message": "Password changed successfully. Please log in with your new password."
}
```

#### Resend Password Change OTP

**Endpoint:** `POST /auth/password-change/resend-otp/`
**Headers:**

```text
X-Api-Key: <your_api_key>
```

**Request Body:**

```json
{
  "email": "user@example.com"
}
```

**Response:** `200 OK`

```json
{
  "message": "Password change verification code has been resent",
  "email": "use***@example.com",
  "expires_in_minutes": 10
}
```

---

### User Profiles "Me" Endpoints

#### Get Authenticated Candidate's Profile

**Endpoint:** `GET /candidates/me/`
**Headers:**

```text
X-Api-Key: <your_api_key>
```

**Required Role:** Any authenticated `candidate`
**Response:** `200 OK`

```json
{
  "user": {
    "id": "4ecxxxxx-8f43-xxxx-xxxx-xxxxxxxxxx",
    "email": "john@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "phone": "+23490xxxxxxxx",
    "date_joined": "2024-01-15T10:30:00Z"
  },
  "school": "Mathematics High School",
  "role": "screening"
}
```

#### Get Authenticated Staff Member's Profile

**Endpoint:** `GET /staff/me/`
**Headers:**

```text
X-Api-Key: <your_api_key>
```

**Required Role:** Any authenticated `staff`
**Response:** `200 OK`

```json
{
  "user": {
    "id": "4ecxxxxx-8f43-xxxx-xxxx-xxxxxxxxxx",
    "email": "jane@example.com",
    "first_name": "Jane",
    "last_name": "Smith",
    "phone": "+23490xxxxxxxx",
    "date_joined": "2024-01-01T08:00:00Z"
  },
  "occupation": "Mathematics Teacher",
  "role": "moderator"
}
```

---

### Candidate Management

#### List Candidates

**Endpoint:** `GET /candidates/`  
**Headers:**

```text
X-Api-Key: <your_api_key>
```

**Required Role:** `moderator` or higher

**Query Parameters:**

- `page` (integer): Page number for pagination
- `search` (string): Search by name, email, or school
- `role` (string): Filter by candidate role
- `school` (string): Filter by school name
- `verified` (boolean): Filter by verification status

**Response:** `200 OK`

```json
{
  "results": [
    {
      "user": {
        "email": "john@example.com",
        "is_email_verified": true,
        "first_name": "John",
        "last_name": "Doe",
        "phone": "+23490xxxxxxxx"
      },
      "school": "Mathematics High School",
      "role": "league",
      "status": "active",
      "is_user_verified": true
    }
  ],
  "pagination": {
    "count": 150,
    "page": 1,
    "page_size": 20,
    "total_pages": 8,
    "has_next": true,
    "has_previous": false,
    "next": "https://api.verboheit.org/v1/candidates/?page=2",
    "previous": null
  }
}
```

#### Get Candidate Details

**Endpoint:** `GET /candidates/{candidate_id}/`
**Headers:**

```text
X-Api-Key: <your_api_key>
Authorization: Bearer <access-token>
```

**Required Role:** `admin` or higher

**Response:** `200 OK`

```json
{
  "user": {
    "id": "17914269-19b2-43f6-aa7e-81e59330df2f",
    "email": "candidate100@mail.com",
    "is_email_verified": true,
    "first_name": "Robert",
    "last_name": "Parker",
    "phone": "08112463722",
    "date_joined": "2025-10-15T11:39:50.742597+01:00"
  },
  "profile_type": "candidate",
  "school": "Porter Ltd High",
  "face_id": null,
  "role": "league",
  "is_active": true,
  "is_user_verified": false,
  "id_card": null,
  "verification_document": null,
  "created_at": "2025-10-15T11:39:51.353736+01:00",
  "updated_at": "2025-10-15T11:39:51.353781+01:00",
  "records": {
    "performance": {
      "stats": {
        "total_score": 141.18,
        "average_score": 70.59,
        "leaderboard_ranking": {
          "current_rank": null,
          "total_candidates": 0
        },
        "latest_score": {
          "score": 99.88,
          "exam_title": "Organized interactive parallelism",
          "date": "2025-10-15T10:40:03.271586Z"
        },
        "highest_score": 99.88,
        "total_exams_taken": 2,
        "lowest_score": 41.3,
        "highest_obtainable_score": 100.0
      },
      "exams_taken": [
        {
          "exam_id": 4,
          "exam_title": "Organized interactive parallelism",
          "exam_stage": "league",
          "scheduled_date": "2025-09-30T10:39:51.622476Z",
          "score": 99.88,
          "recorded_at": "2025-10-15T10:40:03.271586+00:00",
          "score_submitted_by": "Anne Bradshaw",
          "auto_score": false,
          "submission": [
            {
              "question_id": 1,
              "question_text": "What is 2 + 2?",
              "option_a": "3",
              "option_b": "4",
              "option_c": "5",
              "option_d": "6",
              "selected_option": "B",
              "answered_at": "2025-10-15T10:40:03.271586Z"
            }
          ]
        },
        {
          "exam_id": 2,
          "exam_title": "Customizable background utilization",
          "exam_stage": "screening",
          "scheduled_date": "2025-09-17T10:39:51.597446Z",
          "score": 41.3,
          "recorded_at": "2025-10-15T10:40:03.247026+00:00",
          "score_submitted_by": "Kenneth Pace",
          "auto_score": false,
          "submission": [
            {
              "question_id": 2,
              "question_text": "What is 3 + 3?",
              "option_a": "5",
              "option_b": "6",
              "option_c": "7",
              "option_d": "8",
              "selected_option": "B",
              "answered_at": "2025-10-15T10:40:03.247026Z"
            }
          ]
        }
      ]
    },
    "available_exams": []
  }
}
```

#### Assign Candidate Role

**Endpoint:** `PUT /candidates/{candidate_id}/roles/assign/`  
**Headers:**

```text
X-Api-Key: <your_api_key>
```

**Required Role:** `admin` or higher  
**Request Body:**

```json
{
  "role": "league"
}
```

**Response:** `200 OK`

```json
{
  "role": "league"
}
```

_Note: A candidate must be verified before a role can be assigned._

#### Get Candidate Scores

**Endpoint:** `GET /candidates/{candidate_id}/scores/`  
**Required Role:** `admin` or higher  
**Response:** `200 OK`

```json
[
  {
    "id": 1,
    "candidate": {
      "user": {
        "id": "4ecxxxxx-8f43-xxxx-xxxx-xxxxxxxxxx",
        "email": "john@example.com",
        "is_email_verified": true,
        "first_name": "John",
        "last_name": "Doe",
        "phone": "+23490xxxxxxxx",
        "date_joined": "2024-01-15T10:30:00Z"
      },
      "school": "Mathematics High School",
      "role": "league",
      "status": "active",
      "is_user_verified": true
    },
    "exam": {
      "id": 1,
      "title": "Algebra Screening Exam",
      "stage": "screening",
      "question_count": 20,
      "created_at": "2024-01-10T09:00:00Z"
    },
    "score": 88.0,
    "recorded_at": "2024-01-20T15:30:00Z"
  }
]
```

#### Get Candidate Exam History

Retrieves a list of all exams a specific candidate has taken, including their scores and the date of submission. This provides a chronological record of a candidate's performance.

**Endpoint:** `GET /candidates/{candidate_id}/exam-history/`
**Required Role:** 'admin' or higher

**Response:** `200 OK`

```json
[
  {
    "exam": "Algebra Screening Exam",
    "score": 88.0
  },
  {
    "exam": "Geometry Challenge",
    "score": 92.5
  }
]
```

---

### Staff Management

#### List Staff

**Endpoint:** `GET /staff/`  
**Headers:**

```text
X-Api-Key: <your_api_key>
```

**Required Role:** `moderator` or higher

**Query Parameters:**

- `page` (integer): Page number
- `search` (string): Search by name or email
- `role` (string): Filter by staff role
- `occupation` (string): Filter by occupation

**Response:** `200 OK`

```json
{
  "results": [
    {
      "user": {
        "id": "4ecxxxxx-8f43-xxxx-xxxx-xxxxxxxxxx",
        "email": "jane@example.com",
        "is_email_verified": true,
        "first_name": "Jane",
        "last_name": "Smith",
        "phone": "+23490xxxxxxxx",
        "date_joined": "2024-01-01T08:00:00Z"
      },
      "occupation": "Mathematics Teacher",
      "role": "moderator"
    }
  ],
  "pagination": {
    "count": 10,
    "page": 1,
    "page_size": 20,
    "total_pages": 1,
    "has_next": false,
    "has_previous": false,
    "next": null,
    "previous": null
  }
}
```

#### Get Staff Details

**Endpoint:** `GET /staff/{staff_id}/`
**Headers:**

```text
X-Api-Key: <your_api_key>
```

**Required Role:** `manager`, `superadmin`

**Response:** `200 OK`

```json
{
  "user": {
    "id": "4ecxxxxx-8f43-xxxx-xxxx-xxxxxxxxxx",
    "email": "jane@example.com",
    "is_email_verified": true,
    "first_name": "Jane",
    "last_name": "Smith",
    "phone": "+23490xxxxxxxx",
    "date_joined": "2024-01-01T08:00:00Z"
  },
  "profile_type": "staff",
  "occupation": "Mathematics Teacher",
  "face_id": "https://vmlc.s3.amazonaws.com/face_ids/jane_smith.jpg",
  "role": "moderator",
  "is_active": true,
  "is_user_verified": true,
  "id_card": "https://vmlc.s3.amazonaws.com/id_cards/jane_smith_id.pdf?AWSAccessKeyId=...",
  "verification_document": "https://vmlc.s3.amazonaws.com/verification_docs/jane_smith_doc.pdf?AWSAccessKeyId=...",
  "created_at": "2024-01-01T08:00:00Z",
  "updated_at": "2024-01-05T09:00:00Z"
}
```

#### Assign Staff Role

**Endpoint:** `PUT /staff/{staff_id}/roles/assign/`  
**Headers:**

```text
X-Api-Key: <your_api_key>
```

**Required Role:** `manager`, `superadmin`  
**Request Body:**

```json
{
  "role": "admin"
}
```

**Response:** `200 OK`

```json
{
  "role": "admin"
}
```

#### Invite Staff Member

**Endpoint:** `POST /staff/invite/`
**Headers:**

```text
X-Api-Key: <your_api_key>
Authorization: Bearer <access-token>
```

**Required Role:** `manager` or `superadmin`
**Request Body:**

```json
{
  "email": "new.staff@example.com",
  "first_name": "New",
  "last_name": "Staff",
  "phone": "+2349012345678",
  "password": "a_strong_temporary_password",
  "password2": "a_strong_temporary_password",
  "role": "moderator",
  "occupation": "Content Reviewer"
}
```

**Response:** `201 Created`

```json
{
  "message": "Staff profile created, invite sent."
}
```

---

### User Management

#### List Users

**Endpoint:** `GET /user/list/`
**Headers:**

```text
X-Api-Key: <your_api_key>
Authorization: Bearer <access-token>
```

**Required Role:** `moderator` or higher

**Query Parameters:**

- `profile` (string): Filter by user profile type.
  - `candidate`: Returns a list of candidates. Available to `moderator` and higher.
  - `staff`: Returns a list of staff. Available to `manager` and `superadmin` only.
- `is_active` (boolean): Filter by active status.
- `search` (string): Search by name or email.

**Response:** `200 OK`

The response includes a `stats_overview` and a paginated list of users.

- **For `manager` and `superadmin` roles:**
  - Can access `candidate`, `staff`, or the generic user list (by omitting the `profile` parameter).
  - The `stats_overview` will contain full statistics.

- **For `moderator` and `admin` roles:**
  - Can only access the `candidate` list (`profile=candidate`).
  - Accessing the `staff` list or the generic list will result in a `403 Forbidden` error.
  - The `stats_overview` will only contain candidate-related statistics.

**Sample Response (for `manager` or `superadmin`):**

```json
{
  "stats_overview": {
    "total_users": 250,
    "active_users": 230,
    "staff_count": 50,
    "candidate_count": 200
  },
  "results": [
    {
      "id": "4ecxxxxx-8f43-xxxx-xxxx-xxxxxxxxxx",
      "email": "jane@example.com",
      "first_name": "Jane",
      "last_name": "Smith",
      "is_active": true,
      "date_joined": "2024-01-01T08:00:00Z",
      "staff_profile": {
        "occupation": "Mathematics Teacher",
        "role": "moderator"
      },
      "candidate_profile": null
    }
  ],
  "pagination": {
    "count": 1,
    "page": 1,
    "page_size": 20,
    "total_pages": 1,
    "has_next": false,
    "has_previous": false,
    "next": null,
    "previous": null
  }
}
```

_Note: The `stats_overview` provides a summary of user statistics and is regenerated periodically. If it's not available, a message will be displayed._
_When filtered with `profile=candidate` or `profile=staff`, the structure of the items in `results` will match the one from `GET /candidates/` or `GET /staff/` respectively._

---

### Exam Management

The API provides comprehensive management for exams, including CRUD operations, question association, and result viewing.

#### List Exams

**Endpoint:** `GET /exams/`  
**Headers:**

```text
X-Api-Key: <your_api_key>
```

**Required Role:** `admin` or higher

**Query Parameters:**

- `page` (integer): Page number
- `stage` (string): Filter by exam stage (`screening`, `league`, `final`)
- `active` (boolean): Filter by active status
- `date_from` (date): Filter exams from date
- `date_to` (date): Filter exams to date

**Response:** `200 OK`

```json
{
  "question_pool_data": {
    "total_questions": 50,
    "hard_questions_count": 15,
    "moderate_questions_count": 20,
    "easy_questions_count": 15
  },
  "results": [
    {
      "id": 1,
      "title": "Algebra Screening Exam",
      "stage": "screening",
      "level": 1,
      "stage_display": "screening_1",
      "question_count": 20,
      "created_at": "2024-01-10T09:00:00Z",
      "scheduled_date": "2024-01-20T15:00:00Z",
      "status": "concluded",
      "concluded_at": "2024-01-21T15:00:00Z"
    }
  ],
  "pagination": {
    "count": 25,
    "page": 1,
    "page_size": 20,
    "total_pages": 2,
    "has_next": true,
    "has_previous": false,
    "next": "https://api.verboheit.org/v1/exams/?page=2",
    "previous": null
  }
}
```

#### Create Exam

**Endpoint:** `POST /exams/`  
**Headers:**

```text
X-Api-Key: <your_api_key>
```

**Required Role:** `admin` or higher  
**Request Body:**

```json
{
  "title": "New Algebra Exam",
  "stage": "screening",
  "level": 1,
  "description": "A new exam for algebra screening.",
  "scheduled_date": "2025-10-01T10:00:00Z",
  "countdown_minutes": 60,
  "open_duration_hours": 24,
  "is_active": true,
  "questions": [1, 2, 3]
}
```

**Response:** `201 Created`

```json
{
  "id": 4,
  "title": "New Algebra Exam",
  "stage": "screening",
  "level": 1,
  "stage_display": "screening_1",
  "description": "A new exam for algebra screening.",
  "scheduled_date": "2025-10-01T10:00:00Z",
  "countdown_minutes": 60,
  "open_duration_hours": 24,
  "is_active": true,
  "status": "upcoming",
  "concluded_at": null,
  "questions": [1, 2, 3],
  "created_by": {
    "user": {
      "id": "4ecxxxxx-8f43-xxxx-xxxx-xxxxxxxxxx",
      "email": "admin@example.com",
      "first_name": "Admin",
      "last_name": "User",
      "phone": "+23490xxxxxxxx",
      "date_joined": "2024-01-01T08:00:00Z"
    },
    "occupation": "Administrator",
    "role": "superadmin"
  },
  "updated_by": null,
  "average_score": 0.0,
  "created_at": "2025-09-18T12:00:00Z"
}
```

#### Get Exam Details

**Endpoint:** `GET /exams/{exam_id}/`  
**Headers:**

```text
X-Api-Key: <your_api_key>
```

**Required Role:** 'admin' or higher

**Query Parameters:**

- `page` (integer): Page number for questions pagination.
- `page_size` (integer): Number of questions per page.

**Response:** `200 OK`

```json
{
  "id": 1,
  "title": "Algebra Screening Exam",
  "stage": "screening",
  "level": 1,
  "stage_display": "screening_1",
  "description": "Comprehensive algebra exam covering linear equations, polynomials, and systems.",
  "scheduled_date": "2024-01-20T15:00:00Z",
  "countdown_minutes": 90,
  "open_duration_hours": 24,
  "is_active": true,
  "status": "concluded",
  "concluded_at": "2024-01-21T15:00:00Z",
  "questions": {
    "question_pool_data": {
      "total_questions": 3,
      "hard_questions_count": 1,
      "moderate_questions_count": 1,
      "easy_questions_count": 1
    },
    "results": [
      {
        "id": 1,
        "text": "What is 2 + 2?",
        "option_a": "3",
        "option_b": "4",
        "option_c": "5",
        "option_d": "6",
        "correct_answer": "B",
        "difficulty": "easy"
      }
    ],
    "pagination": {
      "count": 3,
      "page": 1,
      "page_size": 10,
      "total_pages": 1,
      "has_next": false,
      "has_previous": false,
      "next": null,
      "previous": null
    }
  },
  "created_by": {
    "user": {
      "id": "4ecxxxxx-8f43-xxxx-xxxx-xxxxxxxxxx",
      "email": "admin@example.com",
      "first_name": "Admin",
      "last_name": "User"
    },
    "occupation": "Administrator",
    "role": "superadmin"
  },
  "updated_by": null,
  "average_score": 78.5,
  "created_at": "2024-01-10T09:00:00Z"
}
```

#### Update Exam

**Endpoint:** `PUT /exams/{exam_id}/` or `PATCH /exams/{exam_id}/`  
**Headers:**

```text
X-Api-Key: <your_api_key>
```

**Required Role:** `admin` or higher  
**Request Body (PATCH example):**

```json
{
  "description": "Updated description for the algebra exam."
}
```

**Response:** `200 OK` (Returns updated exam details)

#### Delete Exam

**Endpoint:** `DELETE /exams/{exam_id}/`  
**Headers:**

```text
X-Api-Key: <your_api_key>
```

**Required Role:** `admin` or higher  
**Response:** `204 No Content`

#### View Exam Questions (Admin/Staff)

**Endpoint:** `GET /exams/{exam_id}/questions/`  
**Headers:**

```text
X-Api-Key: <your_api_key>
```

**Required Role:** 'admin' or higher  
**Response:** `200 OK`

```json
[
  {
    "id": 1,
    "text": "What is 5 × 5?",
    "option_a": "20",
    "option_b": "25",
    "option_c": "205",
    "option_d": "250",
    "correct_answer": "B",
    "difficulty": "easy",
    "created_at": "2024-01-10T09:00:00Z",
    "created_by": {
      "user": {
        "id": "4ecxxxxx-8f43-xxxx-xxxx-xxxxxxxxxx",
        "email": "moderator@example.com",
        "first_name": "Mod",
        "last_name": "User",
        "phone": "+23490xxxxxxxx",
        "date_joined": "2024-01-01T08:00:00Z"
      },
      "occupation": "Moderator",
      "role": "moderator"
    }
  }
]
```

#### Get Exam Results (Admin/Staff)

**Endpoint:** `GET /exams/{exam_id}/results/`
**Headers:**

```text
X-Api-Key: <your_api_key>
```

**Required Role:** 'admin' or higher

**Response:** `200 OK`

```json
[
  {
    "candidate_name": "John Doe",
    "candidate_school": "Mathematics High School",
    "score": 88.0,
    "auto_score": true,
    "score_submitted_by": "Auto Score",
    "recorded_at": "2024-01-20T15:30:00Z"
  }
]
```

#### Candidate Take Exam

Allows an eligible and verified candidate to retrieve the questions for a specific exam.

**Endpoint:** `GET /exams/{exam_id}/take-exam/`  
**Headers:**

```text
X-Api-Key: <your_api_key>
```

**Required Role:** Authenticated `candidate` with `is_user_verified=true` and `role` matching `exam.stage`.  
**Response:** `200 OK`

```json
{
  "id": 1,
  "title": "Algebra Screening Exam",
  "stage": "screening",
  "description": "Comprehensive algebra exam covering linear equations, polynomials, and systems.",
  "open_duration_hours": 12,
  "scheduled_date": "2024-01-20T15:00:00Z",
  "countdown_minutes": 90,
  "questions": [
    {
      "id": 1,
      "text": "What is 5 × 5?",
      "option_a": "20",
      "option_b": "25",
      "option_c": "205",
      "option_d": "250"
    }
  ]
}
```

_Note: This endpoint will return a `403 Forbidden` if the candidate is not verified, their role does not match the exam stage, or the exam is not currently open for submissions._

#### Submit Exam Answers (Candidate)

Allows a candidate to submit their answers for an exam. This endpoint handles bulk submission, performs eligibility checks, prevents re-submission, and triggers asynchronous auto-scoring.

**Endpoint:** `POST /exams/{exam_id}/submit-exam-answers/`  
**Headers:**

```text
X-Api-Key: <your_api_key>
```

**Required Role:** Authenticated `candidate` currently taking the exam.  
**Request Body:**

```json
{
  "answers": [
    {
      "question": 1,
      "selected_option": "B"
    },
    {
      "question": 2,
      "selected_option": "A"
    }
  ]
}
```

_Note: `selected_option` can be an empty string `""` if the question is unanswered._

**Response:** `201 Created`

```json
{
  "message": "Answers submitted successfully!"
}
```

_Note: A `403 Forbidden` will be returned if the exam is closed or the candidate is not eligible. A `400 Bad Request` will be returned if the candidate has already submitted answers for the exam._

---

### Question Management

The API provides CRUD operations for managing exam questions.

#### List Questions

**Endpoint:** `GET /questions/`  
**Required Role:** `moderator` or higher

**Query Parameters:**

- `page` (integer): Page number
- `difficulty` (string): Filter by difficulty (`easy`, `moderate`, `hard`)
- `search` (string): Search question text
- `created_by` (uuid): Filter by the UUID of the staff member who created the question

**Response:** `200 OK`

```json
{
  "question_pool_data": {
    "total_questions": 50,
    "hard_questions_count": 15,
    "moderate_questions_count": 20,
    "easy_questions_count": 15
  },
  "results": [
    {
      "id": 1,
      "text": "What is 5 × 5?",
      "option_a": "20",
      "option_b": "25",
      "option_c": "30",
      "option_d": "35",
      "correct_answer": "B",
      "difficulty": "easy",
      "created_at": "2024-01-10T09:00:00Z",
      "created_by": {
        "user": {
          "id": "4ecxxxxx-8f43-xxxx-xxxx-xxxxxxxxxx",
          "email": "moderator@example.com",
          "first_name": "Mod",
          "last_name": "User"
        },
        "occupation": "Moderator",
        "role": "moderator"
      },
      "updated_at": "2024-01-10T09:00:00Z",
      "updated_by": null
    }
  ],
  "pagination": {
    "count": 50,
    "page": 1,
    "page_size": 20,
    "total_pages": 3,
    "has_next": true,
    "has_previous": false,
    "next": "https://api.verboheit.org/v1/questions/?page=2",
    "previous": null
  }
}
```

#### Create Question

**Endpoint:** `POST /questions/`  
**Required Role:** `moderator` or higher  
**Request Body:**

```json
{
  "text": "What is the capital of France?",
  "option_a": "Berlin",
  "option_b": "Madrid",
  "option_c": "Paris",
  "option_d": "Rome",
  "correct_answer": "C",
  "difficulty": "easy"
}
```

**Response:** `201 Created`

```json
{
  "id": 5,
  "text": "What is the capital of France?",
  "option_a": "Berlin",
  "option_b": "Madrid",
  "option_c": "Paris",
  "option_d": "Rome",
  "correct_answer": "C",
  "difficulty": "easy",
  "created_at": "2025-09-18T12:30:00Z",
  "created_by": {
    "user": {
      "id": "4ecxxxxx-8f43-xxxx-xxxx-xxxxxxxxxx",
      "email": "moderator@example.com",
      "first_name": "Mod",
      "last_name": "User",
      "phone": "+23490xxxxxxxx",
      "date_joined": "2024-01-01T08:00:00Z"
    },
    "occupation": "Moderator",
    "role": "moderator"
  }
}
```

#### Get Question Details

**Endpoint:** `GET /questions/{question_id}/`  
**Required Role:** `moderator` or higher  
**Response:** `200 OK`

```json
{
  "id": 1,
  "text": "What is 5 × 5?",
  "option_a": "20",
  "option_b": "25",
  "option_c": "205",
  "option_d": "250",
  "correct_answer": "B",
  "difficulty": "easy"
  "created_at": "2024-01-10T09:00:00Z",
  "created_by": {
    "user": {
      "id": "4ecxxxxx-8f43-xxxx-xxxx-xxxxxxxxxx",
      "email": "moderator@example.com",
      "first_name": "Mod",
      "last_name": "User",
      "phone": "+23490xxxxxxxx",
      "date_joined": "2024-01-01T08:00:00Z"
    },
    "occupation": "Moderator",
    "role": "moderator"
  }
}
```

#### Update Question

**Endpoint:** `PUT /questions/{question_id}/` or `PATCH /questions/{question_id}/`  
**Required Role:** `moderator` or higher  
**Request Body (PATCH example):**

```json
{
  "difficulty": "moderate"
}
```

**Response:** `200 OK` (Returns updated question details)

#### Delete Question

**Endpoint:** `DELETE /questions/{question_id}/`  
**Required Role:** `moderator` or higher  
**Response:** `204 No Content`
_Note: Questions are soft-deleted by setting `is_archived` to `True` and `archived_at` to the current timestamp._

---

#### Add Question to Exams

**Endpoint:** `POST /questions/{question_id}/exams/`  
**Required Role:** `admin` or higher
**Request Body**:

```json
{
  "add_to_exams": [1, 3, 5],
  "remove_from_exams": [2, 4]
}
```

**Response** `200 OK`:

```json
{
  "question_id": 42,
  "added": [
    { "exam_id": 1, "exam_title": "Math Basics" },
    { "exam_id": 3, "exam_title": "Advanced Math" }
  ],
  "removed": [{ "exam_id": 2, "exam_title": "Science Quiz" }],
  "failed_additions": [{ "exam_id": 5, "reason": "Exam not found" }],
  "failed_removals": []
}
```

#### Bulk Add Questions to Exams

**Endpoint:** `POST /questions/bulk-add-to-exams/`
**Required Role:** `admin` or higher
**Request Body**:

```json
{
  "question_ids": [1, 2, 3, 4, 5],
  "exam_ids": [10, 11]
}
```

**Response** `200 OK`:

```json
{
  "summary": {
    "total_operations": 10,
    "successful": 8,
    "skipped": 1,
    "failed": 1
  },
  "details": {
    "added": [
      { "question_id": 1, "exam_id": 10, "exam_title": "Algebra I" },
      { "question_id": 1, "exam_id": 11, "exam_title": "Algebra II" }
    ],
    "skipped": [
      {
        "question_id": 2,
        "exam_id": 10,
        "exam_title": "Algebra I",
        "reason": "Already exists"
      }
    ],
    "failed_questions": [
      { "question_id": 3, "reason": "Question not found or archived" }
    ],
    "failed_exams": [{ "exam_id": 12, "reason": "Exam not found" }]
  }
}
```

#### Bulk Archive Questions

**Endpoint:** `POST /questions/bulk-archive/`
**Required Role:** `admin` or higher
**Request Body**:

```json
{
  "question_ids": [1, 2, 3]
}
```

**Response** `200 OK`:

```json
{
  "summary": {
    "total_questions": 3,
    "successful_archives": 2,
    "failed_archives": 1
  },
  "details": {
    "archived": [1, 2],
    "failed": [
      { "question_id": 3, "reason": "Question not found or already archived" }
    ]
  }
}
```

### Dashboard

Personalized dashboards provide an overview of relevant information for both candidates and staff members. Dashboard data is cached for performance and updated asynchronously.

#### Candidate Dashboard

**Endpoint:** `GET /dashboard/candidate/`  
**Headers:**

```text
X-Api-Key: <your_api_key>
```

**Required Role:** Any authenticated `candidate`  
**Response:** `200 OK`

```json
{
  "candidate_info": {
    "name": "Harvey Spectre",
    "email": "harvey@gmail.com",
    "phone": "+23490xxxxxxxx",
    "school": "Real Harvard Law",
    "role": "Screening",
    "is_user_verified": false,
    "is_email_verified": true,
    "is_active": true,
    "date_joined": "2024-01-15T10:30:00Z"
  },
  "exam_stats": {
    "total_exams_taken": 3,
    "available_exams_count": 2,
    "average_score": 87.5,
    "highest_score": 95.0,
    "lowest_score": 78.0,
    "latest_score": {
      "score": 99.88,
      "exam_title": "Organized interactive parallelism",
      "date": "2025-10-15T10:40:03.271586Z"
    }
  },
  "leaderboard_ranking": {
    "current_rank": 15,
    "total_candidates": 150
  },
  "recent_scores": [
    {
      "exam_title": "Algebra Screening",
      "score": 88.0,
      "date": "2024-01-20T15:30:00Z",
      "exam_stage": "league"
    }
  ],
  "available_exams": [
    {
      "id": 2,
      "title": "Geometry Screening",
      "stage": "screening",
      "level": 1,
      "stage_display": "screening_1",
      "description": "Comprehensive geometry exam covering shapes, angles, and spatial reasoning.",
      "open_duration_hours": 12,
      "scheduled_date": "2024-01-25T14:00:00Z",
      "countdown_minutes": 90,
      "question_count": 25,
      "participation": "not_done"
    }
  ],
  "concluded_exams": [
    {
      "id": 1,
      "title": "Algebra Screening",
      "stage": "screening",
      "level": 1,
      "stage_display": "screening_1",
      "description": "Comprehensive algebra exam.",
      "concluded_at": "2024-01-21T15:00:00Z",
      "question_count": 20,
      "participation": "missed"
    }
  ]
}
```

_Note:_

- _If dashboard data is not immediately available (e.g., first load), a `202 Accepted` response will be returned, indicating that the data is being generated asynchronously._
- _participation is either missed, done, or not done_

#### Staff Dashboard

**Endpoint:** `GET /dashboard/staff/`  
**Headers:**

```text
X-Api-Key: <your_api_key>
```

**Required Role:** `moderator` or higher  
**Response:** `200 OK`

```json
{
  "staff_info": {
    "name": "Emmanuel Obama",
    "email": "emmaob@gmail.com",
    "role": "Moderator",
    "occupation": "Automation Engineer",
    "is_user_verified": true,
    "is_email_verified": true,
    "is_active": true,
    "date_joined": "2024-01-01T08:00:00Z"
  },
  "candidates": {
    "total": 150,
    "active": 142,
    "verified": 130,
    "recent_registrations": 15,
    "by_role": {
      "screening": { "count": 85 },
      "league": { "count": 45 },
      "final": { "count": 15 },
      "winner": { "count": 5 }
    },
    "verification_rate": 86.7
  },
  "exams": {
    "total": 25,
    "active": 8,
    "recent": 3
  },
  "questions": {
    "total": 500,
    "by_difficulty": {
      "easy": { "count": 200 },
      "moderate": { "count": 200 },
      "hard": { "count": 100 }
    }
  },
  "scores": {
    "total_submissions": 1250,
    "recent_submissions": 45,
    "average_score": 78.5,
    "highest_score": 98.0
  },
  "upcoming_exams": [
    {
      "id": 3,
      "title": "Geometry Screening",
      "scheduled_date": "2024-01-25T14:00:00Z",
      "is_active": true,
      "stage": "screening",
      "question_count": 25,
      "countdown_minutes": 90
    }
  ]
}
```

_Note: Similar to the candidate dashboard, a `202 Accepted` response may be returned if data is being generated asynchronously._

---

### Scoring & Submissions

#### Submit Exam Answers (Candidate)

Allows a candidate to submit their answers for an exam. This endpoint handles bulk submission, performs eligibility checks, prevents re-submission, and triggers asynchronous auto-scoring.

**Endpoint:** `POST /exams/{exam_id}/submit-exam-answers/`  
**Headers:**

```text
X-Api-Key: <your_api_key>
```

**Required Role:** Authenticated `candidate` currently taking the exam.  
**Request Body:**

```json
{
  "answers": [
    {
      "question": 1,
      "selected_option": "B"
    },
    {
      "question": 2,
      "selected_option": "A"
    }
  ]
}
```

_Note: `selected_option` can be an empty string `""` if the question is unanswered._

**Response:** `201 Created`

```json
{
  "message": "Answers submitted successfully!"
}
```

_Note: A `403 Forbidden` will be returned if the exam is closed or the candidate is not eligible. A `400 Bad Request` will be returned if the candidate has already submitted answers for the exam._

#### Submit Exam Score (Manual by Staff)

Allows 'admin' or higher staff members to manually submit or update a candidate's score for a specific exam.

**Endpoint:** `PUT /exams/{exam_id}/submit-exam-score/`
**Headers:**

```text
X-Api-Key: <your_api_key>
```

**Required Role:** `admin` or higher
**Request Body:**

```json
{
  "candidate_id": "4ecxxxxx-8f43-xxxx-xxxx-xxxxxxxxxx",
  "score": 95.5
}
```

**Response:** `200 OK`

```json
{
  "message": "Score updated.",
  "data": {
    "candidate": "John Doe",
    "exam": "Algebra Screening Exam",
    "score": 95.5
  }
}
```

_Note: If the score is being submitted for the first time, the message will be "Score submitted."_

---

### Leaderboard

The leaderboard provides access to performance rankings for exams. It is accessible to all verified staff and candidates with a role of `league` or higher. `screening` candidates can only view screening leaderboards.

#### Publish Leaderboard

Triggers an asynchronous task to refresh and publish the latest leaderboard snapshot. This is a global action that regenerates snapshots for all applicable exams.

**Endpoint:** `POST /leaderboard/publish/`
**Required Role:** `admin` or higher
**Request Body:** None

**Response:** `202 Accepted`

```json
{
  "message": "Leaderboard generation has been started and will be available shortly."
}
```

---

#### Load Leaderboard Data

This endpoint has two modes: summary and detail.

**1. Summary Mode: List Available Leaderboards**

When called without query parameters, it returns a summary of all published leaderboards accessible to the user.

**Endpoint:** `GET /leaderboard/`
**Required Role:** Any verified `candidate` or `staff`.

**Response:** `200 OK`

```json
{
  "snapshot_id": 1,
  "published_at": "2025-11-12T12:00:00Z",
  "available_leaderboards": [
    {
      "stage": "screening",
      "level": 1,
      "stage_display": "screening_1",
      "exam_title": "Screening Exam - Level 1",
      "total_candidates": 50,
      "average_score": 75.5
    },
    {
      "stage": "league",
      "level": 1,
      "stage_display": "league_1",
      "exam_title": "League Competition - Level 1",
      "total_candidates": 25,
      "average_score": 88.0
    }
  ]
}
```

_Note: `screening` candidates will only see leaderboards for the `screening` stage._

**2. Detail Mode: Get Specific Leaderboard**

When `stage` and `level` query parameters are provided, it returns the detailed, paginated rankings for that specific leaderboard.

**Endpoint:** `GET /leaderboard/?stage=<stage>&level=<level>`
**Required Role:** Any verified `candidate` or `staff`.

**Query Parameters:**

- `stage` (string, required): The stage of the leaderboard (e.g., `screening`, `league`).
- `level` (integer, required): The level within the stage (e.g., `1`, `2`).
- `page` (integer, optional): The page number for the `remaining_candidates` list.

**Response:** `200 OK`

```json
{
    "exam_details": {
        "id": 1,
        "title": "League Competition - Level 1",
        "stage": "league",
        "level": 1,
        "scheduled_date": "2025-11-01T10:00:00Z",
        "concluded_at": "2025-11-01T12:00:00Z",
        "total_questions": 50,
        "total_candidates": 25,
        "average_score": 88.0
    },
    "top_three": [
        { "rank": 1, "candidate": { "...details..." }, "score": 99.0 },
        { "rank": 2, "candidate": { "...details..." }, "score": 98.5 },
        { "rank": 3, "candidate": { "...details..." }, "score": 98.0 }
    ],
    "remaining_candidates": [
        { "rank": 4, "candidate": { "...details..." }, "score": 97.0 }
    ],
    "pagination": {
        "count": 22,
        "page": 1,
        "page_size": 20,
        "total_pages": 2,
        "has_next": true,
        "has_previous": false,
        "next": "/leaderboard/?stage=league&level=1&page=2",
        "previous": null
    }
}
```

---

#### Load Candidate Performance Detail

Retrieves the detailed performance of a single candidate for a specific exam leaderboard.

**Endpoint:** `GET /leaderboard/<stage>/<level>/candidate/<candidate_id>/`
**Required Role:**

- `staff` and `league` (or higher) candidates can view any candidate's detail.
- `screening` candidates can only view their own detail.

**URL Parameters:**

- `stage` (string): The stage of the leaderboard (e.g., `screening`).
- `level` (integer): The level of the leaderboard (e.g., `1`).
- `candidate_id` (integer): The ID of the candidate.

**Response:** `200 OK`

```json
{
  "exam_details": {
    "id": 1,
    "title": "League Competition - Level 1",
    "stage": "league",
    "level": 1,
    "scheduled_date": "2025-11-01T10:00:00Z",
    "concluded_at": "2025-11-01T12:00:00Z",
    "total_questions": 50,
    "total_candidates": 25,
    "average_score": 88.0
  },
  "candidate_performance": {
    "rank": 1,
    "candidate": {
      "id": 101,
      "full_name": "John Doe",
      "school": "Innovation High"
    },
    "score": 99.0,
    "submissions": [
      {
        "question_id": 1,
        "question_text": "What is 2+2?",
        "option_a": "A",
        "option_b": "B",
        "option_c": "D",
        "option_d": "C",
        "correct_answer": "C",
        "selected_option": "C",
        "is_correct": true
      }
    ],
    "participated_at": "2025-11-01T10:15:30Z"
  }
}
```

### User Verification

The user verification endpoints allow staff members to manage the verification process for all users.

#### Get User's Verification Status

**Endpoint:** `GET /user/verification/status/`
**Required Role:** Any authenticated user
**Description:** Retrieves the verification status of the currently authenticated user.
**Response:** `200 OK`

```json
{
  "is_approved": true,
  "is_rejected": false,
  "is_pending": false,
  "rejection_reason": null
}
```

#### Get Another User's Verification Status

**Endpoint:** `GET /user/verification/status/{user_id}/`
**Required Role:** `manager` or `superadmin`, or the user themselves
**Description:** Retrieves the verification status for a specific user.
**Response:** `200 OK` (Same as above)

#### Upload/Resubmit Verification Documents

**Endpoint:** `POST /user/verification/upload/` or `PATCH /user/verification/upload/`
**Required Role:** Any authenticated user
**Description:** Allows a user to submit or resubmit their verification documents. This is a `multipart/form-data` request.
**Request Body:**

- `face_id`: Image file
- `id_card`: Image or PDF file
- `verification_document`: Image or PDF file
  **Response:** `200 OK` or `201 Created`

#### List Verification Requests

**Endpoint:** `GET /user/verification/list/`
**Required Role:** `manager` or `superadmin`
**Description:** Retrieves a list of verification requests, with filters for status.
**Query Parameters:**

- `is_pending` (boolean)
- `is_approved` (boolean)
- `is_rejected` (boolean)
  **Response:** `200 OK` (Paginated list of user verification objects)

#### Approve or Reject a Verification Request

**Endpoint:** `POST /user/verification/action/{id}/`
**Required Role:** `manager` or `superadmin`
**Description:** Allows a staff member to approve or reject a user's verification application.
**Request Body:**
To approve:

```json
{
  "is_approved": true
}
```

To reject:

```json
{
  "is_rejected": true,
  "rejection_reason": "The provided ID card was not clear."
}
```

_Note: `rejection_reason` is optional when rejecting._
**Response:** `200 OK`

```json
{
  "message": "User verification has been updated successfully"
}
```

#### Download Verification Documents

**Endpoint:** `GET /user/verification/documents/{type}/{id}/`
**Required Role:** `manager` or `superadmin`, or the user themselves
**Description:** Provides a secure, temporary URL to download a user's verification document.
**Path Parameters:**

- `type`: One of `face_id`, `id_card`, `verification_document`
- `id`: The User ID
  **Response:** `200 OK`

```json
{
  "url": "https://<s3_bucket_url>/.../file.jpg?AWSAccessKeyId=..."
}
```

---

### Account Management

This endpoint allows users to retrieve and update their own account information. Staff members with `manager` or `superadmin` roles can also manage other users' accounts.

#### Get User Account

**Endpoint:** `GET /account-management/{user_id}/`
**Headers:**

```text
X-Api-Key: <your_api_key>
Authorization: Bearer <access-token>
```

**Required Role:** Authenticated User (for their own account), `manager` or `superadmin` (for other accounts).

If `user_id` is not provided, it defaults to the current authenticated user.

**Response:** `200 OK`

```json
{
  "profile": {
    "user": {
      "id": "4ecxxxxx-8f43-xxxx-xxxx-xxxxxxxxxx",
      "email": "john@example.com",
      "is_email_verified": true,
      "first_name": "John",
      "last_name": "Doe",
      "profile_picture": "https://vmlc.s3.amazonaws.com/profile_pictures/john_doe.jpg",
      "phone": "+23490xxxxxxxx",
      "date_joined": "2024-01-15T10:30:00Z"
    },
    "occupation": "Mathematics Teacher",
    "face_id": "https://vmlc.s3.amazonaws.com/face_ids/jane_smith.jpg",
    "role": "moderator",
    "is_active": true,
    "is_user_verified": true,
    "id_card": "https://vmlc.s3.amazonaws.com/id_cards/john_smith_id.pdf?AWSAccessKeyId=...",
    "verification_document": "https://vmlc.s3.amazonaws.com/verification_docs/john_smith_doc.pdf?AWSAccessKeyId=...",
    "created_at": "2024-01-01T08:00:00Z",
    "updated_at": "2024-01-05T09:00:00Z"
  }
}
```

#### Update User Account

**Endpoint:** `PATCH /account-management/{user_id}/`
**Headers:**

```text
X-Api-Key: <your_api_key>
Authorization: Bearer <access-token>
Content-Type: multipart/form-data
```

**Required Role:** Authenticated User (for their own account), `manager` or `superadmin` (for other accounts).

If `user_id` is not provided, it defaults to the current authenticated user.

**Request Body (form-data):**

- `first_name` (string, optional)
- `last_name` (string, optional)
- `profile_picture` (file, optional)
- `phone` (string, optional)
- `school` (string, optional, for candidates)
- `occupation` (string, optional, for staff)

**Response:** `200 OK`

```json
{
  "message": "Account updated successfully.",
  "profile": {
     ... updated profile data ...
  }
}
```

#### Get Account Details (Admin)

**Endpoint:** `GET /account-management/{user_id}/`
**Headers:**

```text
X-Api-Key: <your_api_key>
```

**Required Role:** `manager` or higher

**Response:** `200 OK`

```json
{
  "profile": {
    "user": {
      "id": "4ecxxxxx-8f43-xxxx-xxxx-xxxxxxxxxx",
      "email": "jane@example.com",
      "is_email_verified": true,
      "first_name": "Jane",
      "last_name": "Smith",
      "phone": "+23490xxxxxxxx",
      "date_joined": "2024-01-01T08:00:00Z"
    },
    "occupation": "Mathematics Teacher",
    "face_id": "https://vmlc.s3.amazonaws.com/face_ids/jane_smith.jpg",
    "role": "moderator",
    "is_active": true,
    "is_user_verified": true,
    "id_card": "https://vmlc.s3.amazonaws.com/id_cards/jane_smith_id.pdf?AWSAccessKeyId=...",
    "verification_document": "https://vmlc.s3.amazonaws.com/verification_docs/jane_smith_doc.pdf?AWSAccessKeyId=...",
    "created_at": "2024-01-01T08:00:00Z",
    "updated_at": "2024-01-05T09:00:00Z"
  }
}
```

_Note: The structure of the `profile` object will vary based on whether the user is a candidate or staff._

#### Update Account Details

Allows authenticated users to update their own account and profile information. Superadmins can update other users' accounts.

**Endpoint:** `PATCH /account-management/` (for self) or `PATCH /account-management/{user_id}/` (for superadmins)
**Headers:**

```text
X-Api-Key: <your_api_key>
```

**Required Role:** Any authenticated user (for self), `manager` or higher (for others)
**Request Body (example):**

```json
{
  "user": {
    "first_name": "Jonathan"
  },
  "profile": {
    "school": "New High School"
  }
}
```

_Note: You can update `user` fields, `profile` fields, or both. The `profile` fields will depend on whether the user is a candidate or staff._

**Response:** `200 OK`

```json
{
  "message": "Account updated successfully.",
  "profile": {
    "user": {
      "id": "4ecxxxxx-8f43-xxxx-xxxx-xxxxxxxxxx",
      "email": "john@example.com",
      "is_email_verified": true,
      "first_name": "Jonathan",
      "last_name": "Doe",
      "phone": "+23490xxxxxxxx",
      "date_joined": "2024-01-15T10:30:00Z"
    },
    "school": "New High School",
    "face_id": "https://vmlc.s3.amazonaws.com/face_ids/john_doe.jpg",
    "role": "league",
    "is_active": true,
    "is_user_verified": true,
    "id_card": "https://vmlc.s3.amazonaws.com/id_cards/john_doe_id.pdf?AWSAccessKeyId=...",
    "verification_document": "https://vmlc.s3.amazonaws.com/verification_docs/john_doe_doc.pdf?AWSAccessKeyId=...",
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-20T11:00:00Z",
    "scores": {
      "total_score": 380.0,
      "average_score": 95.0,
      "scores": [
        {
          "exam_id": 1,
          "exam_title": "Algebra Screening",
          "score": 88.0,
          "recorded_at": "2024-01-20T15:30:00Z",
          "score_submitted_by": "Auto Score",
          "auto_score": true
        }
      ]
    }
  }
}
```

---

### Notifications with WebSockets

Clients receive notifcations usin WebSockets. For example, [broadcasts](#create-broadcast) made via the `platform` medium at target users (or roles) will come through the notifications endpoint, allowing clients to receive instant updates without needing to poll the server.

#### Real-time Notifications

Connect to this endpoint to receive `platform` notifications in real-time.

**Endpoint:** `ws://<host>/v1/ws/notifications/` (preferrably `wss://` for secure connections in production)

**Headers:**

```text
X-Api-Key: <your_api_key>
Authorization: Bearer <access_token>
```

**Required Role:** Any authenticated user (for self)

**Receiving Messages (Server-to-Client):**
When a new notification is generated for the authenticated user (e.g., via a broadcast), the server will push a JSON message with the following structure:

```json
{
  "type": "notification_activity",
  "message": {
    "id": 123,
    "subject": "New Exam Available",
    "message": "The final stage exam is now open. Good luck!",
    "read": false,
    "created_at": "2025-09-21T12:00:00.123456Z"
  }
}
```

**Sending Messages (Client-to-Server):**
Clients can send messages to the server to perform actions, like `mark_as_read`. The message must be a JSON object with an `action` and a `data` payload.

**Action: `mark_as_read`**
Marks a specific notification as read.

**Request Payload:**

```json
{
  "action": "mark_as_read",
  "data": {
    "notification_id": 123
  }
}
```

**Server Response:**
If the action is unknown or the payload is invalid, the server will send back an error message:

```json
{
  "type": "error",
  "message": "Unknown action: <action_name>"
}
```

---

### Broadcast Management

The broadcast system allows authorized staff to send targeted communications to users (candidates and/or staff). Broadcasts are sent asynchronously, and their status can be tracked.

#### List Broadcasts

**Endpoint:** `GET /broadcasts/`
**Headers:**

```text
X-Api-Key: <your_api_key>
Authorization: Bearer <access_token>
```

**Required Role:** `manager` or higher

**Response:** `200 OK`

```json
{
  "count": 1,
  "total_pages": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "subject": "Important Announcement",
      "message": "Please review the new exam schedule.",
      "created_by": {
        "user": {
          "email": "manager@example.com",
          "first_name": "Manager",
          "last_name": "User"
        },
        "occupation": "System Manager",
        "role": "manager"
      },
      "created_at": "2025-09-20T10:00:00Z",
      "mediums": ["email", "platform"],
      "target_roles": {
        "candidate": ["league", "final"],
        "staff": ["moderator", "volunteer"]
      }
    }
  ]
}
```

#### Create Broadcast

**Endpoint:** `POST /broadcasts/`
**Headers:**

```text
X-Api-Key: <your_api_key>
Authorization: Bearer <access_token>
```

**Required Role:** `manager` or higher
**Request Body:**

```json
{
  "subject": "New Exam Available",
  "message": "The final stage exam is now open. Good luck!",
  "mediums": ["email", "platform"],
  "target_roles": {
    "staff": ["volunteer", "moderator"],
    "candidate": ["final"]
  }
}
```

_Note: The `target_roles` object must contain either a `staff` key, a `candidate` key, or both. The values should be arrays of valid roles._

- _Valid `staff` roles: `volunteer`, `moderator`, `admin`, `manager`, `superadmin`_
- _Valid `candidate` roles: `screening`, `league`, `final`, `winner`_

**Response:** `201 Created`

```json
{
  "id": 2,
  "task_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
  "subject": "New Exam Available",
  "message": "The final stage exam is now open. Good luck!",
  "created_by": { "...": "..." },
  "created_at": "2025-09-21T12:00:00Z",
  "status": "pending",
  "mediums": ["email", "platform"],
  "target_roles": {
    "staff": ["volunteer", "moderator"],
    "candidate": ["final"]
  },
  "logs": []
}
```

_Note: Creating a broadcast triggers an asynchronous task. The response includes the task_id for tracking. If platform is a medium, a real-time notification will be pushed to connected clients via WebSockets._

#### Get Broadcast Details



**Endpoint:** `GET /broadcasts/{broadcast_id}/`  

**Required Role:** `manager` or higher

_Note: The response for this endpoint is cached for performance. The cache is invalidated when the broadcast sending task completes._

**Response:** `200 OK` (Returns the detailed broadcast object, including the status and logs of sending attempts)



---



### Webhooks



This section details API endpoints designed to receive automated notifications or data from other services.



#### Database Backup Webhook



This webhook endpoint is designed to receive status updates from the database backup script. It provides a way to monitor the success or failure of backup operations.



**Endpoint:** `POST /webhooks/db-backup/`

**Headers:**



```text

X-Api-Key: <your_api_key>

```



**Required Role:** None (API Key only)

**Request Body:**



```json

{

  "status": "success",

  "environment": "prod",

  "timestamp": "2025-01-01T12:00:00Z",

  "backup_filename": "db_backup_2025-01-01.sql",

  "error_message": null

}

```



- `status` (string): The status of the backup operation (`success`, `first_failure`, `final_failure`).

- `environment` (string): The environment where the backup was performed (`prod`, `staging`).

- `timestamp` (string): ISO 8601 formatted timestamp of the backup event.

- `backup_filename` (string): The name of the backup file.

- `error_message` (string, optional): Details of the error if the backup failed.



**Response:** `200 OK`



```json

{

  "status": "received"

}

```



---



## Advanced Topics

### Query Parameters

#### Common Parameters

| Parameter  | Type    | Description                                              | Example                 |
| ---------- | ------- | -------------------------------------------------------- | ----------------------- |
| `page`     | integer | Page number for pagination                               | `?page=2`               |
| `limit`    | integer | Items per page (max: 100)                                | `?limit=25`             |
| `search`   | string  | Search across relevant fields (e.g., name, email, title) | `?search=john`          |
| `ordering` | string  | Sort results (`field` or `-field` for descending)        | `?ordering=-created_at` |

#### Filtering Parameters

| Endpoint                   | Parameter     | Type    | Description                                                         |
| -------------------------- | ------------- | ------- | ------------------------------------------------------------------- |
| `/candidates/`             | `role`        | string  | Filter by candidate role (`screening`, `league`, `final`, `winner`) |
| `/candidates/`             | `school`      | string  | Filter by school name                                               |
| `/candidates/`             | `verified`    | boolean | Filter by verification status (`true` or `false`)                   |
| `/staff/`                  | `role`        | string  | Filter by staff role (`volunteer`, `moderator` or higher)           |
| `/staff/`                  | `occupation`  | string  | Filter by occupation                                                |
| `/exams/`                  | `stage`       | string  | Filter by exam stage (`screening`, `league`)                        |
| `/exams/`                  | `active`      | boolean | Filter by active status (`true` or `false`)                         |
| `/questions/`              | `difficulty`  | string  | Filter by question difficulty (`easy`, `moderate`, `hard`)          |
| `/questions/`              | `created_by`  | uuid    | Filter by the UUID of the staff member who created the question     |
| `/user/verification/list/` | `is_pending`  | boolean | Filter by pending verification status                               |
| `/user/verification/list/` | `is_approved` | boolean | Filter by verified status                                           |
| `/user/verification/list/` | `is_rejected` | boolean | Filter by rejected status                                           |

#### Date Filtering

Use ISO 8601 format for date parameters:

| Parameter        | Format              | Example                               |
| ---------------- | ------------------- | ------------------------------------- |
| `date_from`      | YYYY-MM-DD          | `?date_from=2024-01-01`               |
| `date_to`        | YYYY-MM-DD          | `?date_to=2024-12-31`                 |
| `created_after`  | YYYY-MM-DDTHH:MM:SS | `?created_after=2024-01-01T10:00:00`  |
| `created_before` | YYYY-MM-DDTHH:MM:SS | `?created_before=2024-01-01T10:00:00` |

---

## Error Handling

### Standardized Error Response

The API returns errors in a standardized format to ensure consistency and ease of parsing. All error responses follow this structure:

```json
{
  "detail": "Error message describing the issue.",
  "code": "error_code"
}
```

- **detail**: A human-readable message explaining the error.
- **code**: A unique code for the specific error type.

### HTTP Status Codes

| Code | Status                | Description                                                                                                        |
| ---- | --------------------- | ------------------------------------------------------------------------------------------------------------------ |
| 200  | OK                    | Request successful.                                                                                                |
| 201  | Created               | Resource created successfully.                                                                                     |
| 202  | Accepted              | Request accepted for processing, but the processing is not yet complete (e.g., asynchronous task).                 |
| 204  | No Content            | Resource deleted successfully or action completed with no content to return.                                       |
| 400  | Bad Request           | Invalid input, such as a malformed request body or invalid parameters.                                             |
| 401  | Unauthorized          | Authentication credentials were not provided or were invalid.                                                      |
| 403  | Forbidden             | You do not have permission to perform this action (e.g., insufficient role, unverified account, feature disabled). |
| 404  | Not Found             | The requested resource could not be found.                                                                         |
| 429  | Too Many Requests     | You have exceeded the rate limit.                                                                                  |
| 500  | Internal Server Error | An unexpected error occurred on the server.                                                                        |
| 502  | Bad Gateway           | The server received an invalid response from an upstream server (e.g., S3 error).                                  |

### Common Error Codes

| Code                            | Description                                                                          |
| ------------------------------- | ------------------------------------------------------------------------------------ |
| `authentication_failed`         | Incorrect authentication credentials.                                                |
| `not_authenticated`             | Authentication credentials were not provided.                                        |
| `permission_denied`             | You do not have permission to perform this action.                                   |
| `not_found`                     | The requested resource could not be found.                                           |
| `invalid`                       | Invalid input (e.g., validation errors in request body).                             |
| `invalid_token`                 | Token is invalid or expired.                                                         |
| `rate_limit_exceeded`           | You have exceeded the rate limit.                                                    |
| `no_recipients_found`           | A broadcast operation found no recipients for the specified target.                  |
| `invalid_medium`                | The specified broadcast medium is invalid or not implemented.                        |
| `registration_closed`           | Registration for this type of user is currently disabled by a feature flag.          |
| `email_not_verified`            | User's email address has not been verified.                                          |
| `already_verified`              | User is already verified and cannot resubmit verification documents.                 |
| `pending_verification`          | User has a pending verification request and cannot submit a new one (for POST).      |
| `unverified_candidate`          | Candidate must be verified to perform this action (e.g., take an exam, assign role). |
| `unverified_staff`              | Staff member must be verified to perform this action.                                |
| `exam_not_open`                 | The exam is not currently open for submissions.                                      |
| `exam_not_eligible`             | The candidate's role does not match the exam stage.                                  |
| `exam_already_submitted`        | The candidate has already submitted answers for this exam.                           |
| `invalid_file_type`             | The uploaded file has an unsupported extension.                                      |
| `file_size_exceeded`            | The uploaded file exceeds the maximum allowed size.                                  |
| `leaderboard_hidden`            | The leaderboard is currently not visible to the public.                              |
| `leaderboard_not_published`     | The leaderboard has not been published yet.                                          |
| `account_already_authenticated` | An authenticated user attempted to register a new account.                           |
| `invalid_otp`                   | The provided One-Time Password is invalid or expired.                                |
| `passwords_do_not_match`        | New password and confirmation password do not match.                                 |
| `password_validation_failed`    | The new password does not meet security requirements.                                |

---

## Rate Limiting

### Rate Limit Policy

**Authenticated Users:**

- 1000 requests per day
- 60 requests per hour
- 10 requests per minute

**Anonymous Users:**

- 60 requests per day
- 5 requests per minute

### Rate Limit Headers

When a rate limit is applied, the following headers are included in the response:

```text
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1640995200
```

- `X-RateLimit-Limit`: The maximum number of requests allowed in the current period.
- `X-RateLimit-Remaining`: The number of requests remaining in the current period.
- `X-RateLimit-Reset`: The UTC epoch seconds when the current rate limit window resets.

### Rate Limit Exceeded

If you exceed the allocated rate limit, the API will return a `429 Too Many Requests` response:
**Response:** `429 Too Many Requests`

```json
{
  "detail": "Request was throttled. Expected available in 10 seconds.",
  "code": "throttle_exceeded"
}
```

_Note: The exact `detail` message and `code` might vary slightly based on the throttling implementation._

---

## Versioning

### Current Version

The API is currently at version `v1`. All endpoints are prefixed with `/v1/`.

### Versioning Strategy

- **Backwards Compatibility**: Minor changes maintain backwards compatibility.
- **Breaking Changes**: Major version increments for breaking changes.
- **Deprecation**: 6-month notice period for deprecated endpoints.
- **Version Support**: Latest 2 major versions supported.

---

## Support

## Interactive Documentation

Explore the API interactively using our documentation interfaces, automatically generated from the API schema:

- **Swagger UI**: `https://api.verboheit.org/v1/docs/swagger/`
- **ReDoc**: `https://api.verboheit.org/v1/docs/redoc/`

---

## Support

For technical support, API key requests, or questions:

- **Email:** `theolujay@gmail.com`
- **Discord:** `@olujay`
- **X:** `@theolujay`
- **Response Time:** Within 48 hours for support requests.

## Changelog

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
        _Leaderboard_
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
    - _Breaking Change:_ Modified the leaderboard generation and retrieval process.
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

- **Exam Results & Candidate Details** \*\*Renamed `submitted_by` to `score_submitted_by`
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
