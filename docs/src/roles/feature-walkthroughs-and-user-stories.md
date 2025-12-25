# Feature Walkthroughs and User Stories

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
- `PUT /exams/{id}/submit-exam-score/` — manual score submission (admin). `200 OK`.

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
