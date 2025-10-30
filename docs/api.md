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
  - [Health & Root](#health--root)
  - [Authentication](#authentication-endpoints)
  - [Registration](#registration)
  - [Email & Password](#email--password)
  - [User Profiles ("Me" Endpoints)](#user-profiles-me-endpoints)
  - [Candidate Management](#candidate-management)
  - [Staff Management](#staff-management)
  - [User Verification](#user-verification)
  - [Account Management](#account-management)
  - [Exam Management](#exam-management)
  - [Question Management](#question-management)
  - [Scoring & Submissions](#scoring--submissions)
  - [Dashboard](#dashboard)
  - [Leaderboard](#leaderboard)
  - [Notifications](#notifications)
  - [Broadcast Management](#broadcast-management)
- [Advanced Topics](#advanced-topics)
  - [Query Parameters](#query-parameters)
  - [Error Handling](#error-handling)
  - [Rate Limiting](#rate-limiting)
  - [Versioning](#versioning)
- [Support & More](#support--more)
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

All endpoints are relative to this base URL. A discoverable list of endpoints is available at the [root](#root-endpoint) endpoint.

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
*Note: The `profile` field will contain either `candidate` or `staff` specific data based on the user's role.*

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

## Health & Root

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

### Root Endpoint
The root endpoint provides a discoverable list of all available API endpoints, categorized for easy navigation.

**Endpoint:** `GET /root/`
**Headers:**
```text
X-Api-Key: <your_api_key>
```
**Required Role:** None (Public, but requires API Key)

**Response:** `200 OK`
```json
{
  "root": "https://api.verboheit.org/v1/root/",
  "authentication": {
    "login": "https://api.verboheit.org/v1/auth/login/",
    "logout": "https://api.verboheit.org/v1/auth/logout/",
    "token_refresh": "https://api.verboheit.org/v1/auth/token/refresh/"
  },
  // ... other endpoints ...
}
```

---

## User Roles, Permissions, and API Access

This table provides a detailed breakdown of each user role, its key abilities on the platform, and the primary API endpoints it has access to.

### Candidate User Type

| Role | Key Abilities (What they can do) | Accessible API Endpoints |
|------|-----------------------------------|--------------------------|
| **`screening`** | • View their personal dashboard.<br>• Take screening-level exams.<br>• View their own profile and verification status.<br>• View screening leaderboard snapshots. | • `GET /dashboard/candidate/`<br>• `GET /candidates/me/`<br>• `GET /user/verification/status/`<br>• `POST /user/verification/upload/`<br>• `GET /exams/{id}/take-exam/` (where `stage` is `screening`)<br>• `POST /exams/{id}/submit-exam-answers/`<br>• `GET /load-leaderboard/` (for screening exams) |
| **`league`** | • All `screening` abilities.<br>• Take league-level exams.<br>• View the competition leaderboard snapshots or a specific exam leaderboard. | • All `screening` endpoints.<br>• `GET /load-leaderboard/`<br>• `GET /exams/{id}/take-exam/` (where `stage` is `league`) |
| **`final`** | • All `league` abilities.<br>• Access to (offline) final-stage exams. | • All `league` endpoints.<br>• `GET /exams/{id}/take-exam/` (where `stage` is `final`) |
| **`winner`** | • Ceremonial role with all candidate permissions. Registered winner of the final stage. | • All `final` endpoints. |

### Staff User Type

*(Permissions are hierarchical; higher roles inherit permissions from lower roles)*

| Role | Key Abilities (What they can do) | Newly Accessible API Endpoints (in addition to lower roles) |
|------|-----------------------------------|-------------------------------------------------------------|
| **`volunteer`** | • View their own profile.<br>• Submit their own documents for verification. | • `GET /staff/me/`<br>• `GET /user/verification/status/`<br>• `POST/PATCH /user/verification/upload/` |
| **`admin`** | • View details for any candidate.<br>• Change roles for candidates.<br>• Full management (CRUD) of exams.<br>• Manually submit scores.<br>• Publish leaderboard for a specific exam. | • `GET /candidates/{id}/`<br>• `GET /candidates/{id}/scores/`<br>• `GET /candidates/{id}/exam-history/`<br>• `PUT /candidates/{id}/roles/assign/`<br>• `GET/POST /exams/`<br>• `GET/PUT/PATCH/DELETE /exams/{id}/`<br>• `PUT /exams/{id}/submit-exam-score/`<br>• `POST /publish-leaderboard/` |
| **`manager`** | • View details for any staff member.<br>• Change roles for staff (except `manager` or `superadmin`).<br>• Manage user verifications for candidates and staff members (approve/reject).<br>• Create and view broadcasts. | • `GET /staff/{id}/`<br>• `PUT /staff/{id}/roles/assign/`<br>• `GET /user/verification/list/`<br>• `POST /user/verification/action/{id}/`<br>• `GET /user/verification/documents/{type}/{id}/`<br>• `GET/POST /broadcasts/`<br>• `GET /broadcasts/{id}/`<br>• `GET/PATCH /account-management/{id}/` |
| **`admin`** | • View details for any candidate.<br>• Change roles for candidates.<br>• Full management (CRUD) of exams.<br>• Manually submit scores.<br>• Publish leaderboard for a specific exam. | • `GET /candidates/{id}/`<br>• `GET /candidates/{id}/scores/`<br>• `GET /candidates/{id}/exam-history/`<br>• `PUT /candidates/{id}/roles/assign/`<br>• `GET/POST /exams/`<br>• `GET/PUT/PATCH/DELETE /exams/{id}/`<br>• `PUT /exams/{id}/submit-exam-score/`<br>• `POST /publish-leaderboard/` |
| **`manager`** | • View details for any staff member.<br>• Change roles for staff (except `manager` or `superadmin`).<br>• Manage user verifications for candidates and staff members (approve/reject).<br>• Create and view broadcasts. | • `GET /staff/{id}/`<br>• `PUT /staff/{id}/roles/assign/`<br>• `GET /user/verification/list/`<br>• `POST /user/verification/action/{id}/`<br>• `GET /user/verification/documents/{type}/{id}/`<br>• `GET/POST /broadcasts/`<br>• `GET /broadcasts/{id}/`<br>• `GET/PATCH /account-management/{id}/` |
| **`superadmin`** | • Can assign any staff role (except `superadmin`).<br>• Has full platform control inheriting all permissions. | *(Inherits all `manager` endpoints with zero restrictions)* |
| **`sponsor`** | • A vanity role with no specific permissions. | *(No specific endpoints)* |

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
>     
> - Authenticated user endpoints also require `Authorization: Bearer <access-token>`.
>     
> - Role requirements shown when specified.
>     
> - Use JSON unless `multipart/form-data` is stated.
>     

---

#### Health & discovery

- `GET /health/` — public health check. `200 OK`.
    
- `GET /root/` — discoverable list of endpoints (requires API key). `200 OK`.
    

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
    
- `POST /resend-email-otp/` — resend OTP. `200 OK` (returns masked email + `expires_in_minutes`).
    

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

#### Leaderboard & publishing

- `POST /publish-leaderboard/` — start generation & publish snapshot for a specific exam (admin+). Request: `{ exam_id: <int> }`. `202 Accepted`.
    
- `GET /load-leaderboard/` — fetch latest published snapshot(s). Role: `league` candidates and above, all staff. Query: `exam_id` (optional, to get a specific leaderboard), `limit`, `offset`. `200 OK`.
    

---
</details>

<details>
<summary>Broadcasts & notifications</summary>

- `GET /broadcasts/`, `POST /broadcasts/` — list/create broadcasts. Role: `manager`+. `200/201 OK`.
    
- `GET /broadcasts/{id}/` — view broadcast. `200 OK`.
    
- Note: WebSocket notifications require both `X-Api-Key` and `Authorization` according to changelog.
    

---

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
  "school": "Mathematics High School"
}
```

**Response:** `201 Created`
```json
{
  "message": "Registration successful."
}
```
*Note: If candidate registration is closed, a `403 Forbidden` response will be returned. Kindly reach the developer.*

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
  "occupation": "Mathematics Teacher"
}
```
*Note: If staff registration is closed, a `403 Forbidden` response will be returned.*

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

#### Resend Email OTP
**Endpoint:** `POST /resend-email-otp/`
**Headers:**
```text
X-Api-Key: <your_api_key>
```
**Request Body:**
```json
{
  "email": "john@example.com"
}
```

**Response:** `200 OK`
```json
{
  "message": "OTP has been resent to your email address",
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
  "count": 150,
  "total_pages": 8,
  "next": "https://api.verboheit.org/v1/candidates/?page=2",
  "previous": null,
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
      "is_user_verified": true
    }
  ]
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
*Note: A candidate must be verified before a role can be assigned.*

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
  "count": 10,
  "total_pages": 1,
  "next": null,
  "previous": null,
  "results": [
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
  ]
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
  "total_pages": 2,
  "next": "https://api.verboheit.org/v1/exams/?page=2",
  "previous": null,
  "list": [
    {
      "id": 1,
      "title": "Algebra Screening Exam",
      "stage": "screening",
      "question_count": 20,
      "created_at": "2024-01-10T09:00:00Z"
    }
  ]
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
  "description": "A new exam for algebra screening.",
  "scheduled_date": "2025-10-01T10:00:00Z",
  "countdown_minutes": 60,
  "open_duration_hours": 24,
  "is_active": true,
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
  "description": "Comprehensive algebra exam covering linear equations, polynomials, and systems.",
  "scheduled_date": "2024-01-20T15:00:00Z",
  "countdown_minutes": 90,
  "open_duration_hours": 24,
  "is_active": true,
  "questions": {
    "question_pool_data": {
        "total_questions": 3,
        "hard_questions_count": 1,
        "moderate_questions_count": 1,
        "easy_questions_count": 1
    },
    "count": 3,
    "next": null,
    "previous": null,
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
    ]
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
``````

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
*Note: This endpoint will return a `403 Forbidden` if the candidate is not verified, their role does not match the exam stage, or the exam is not currently open for submissions.*

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
*Note: `selected_option` can be an empty string `""` if the question is unanswered.*

**Response:** `201 Created`
```json
{
  "message": "Answers submitted successfully!"
}
```
*Note: A `403 Forbidden` will be returned if the exam is closed or the candidate is not eligible. A `400 Bad Request` will be returned if the candidate has already submitted answers for the exam.*

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
*Note: If the score is being submitted for the first time, the message will be "Score submitted."*

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
  "total_pages": 5,
  "next": "https://api.verboheit.org/v1/questions/?page=2",
  "previous": null,
  "question_pool_data": {
    "total_questions": 50,
    "hard_questions_count": 15,
    "moderate_questions_count": 20,
    "easy_questions_count": 15
  },
  "list": [
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
  ]
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
*Note: Questions are soft-deleted by setting `is_archived` to `True` and `archived_at` to the current timestamp.*

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
        {"exam_id": 1, "exam_title": "Math Basics"},
        {"exam_id": 3, "exam_title": "Advanced Math"}
    ],
    "removed": [
        {"exam_id": 2, "exam_title": "Science Quiz"}
    ],
    "failed_additions": [
        {"exam_id": 5, "reason": "Exam not found"}
    ],
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
            {"question_id": 1, "exam_id": 10, "exam_title": "Algebra I"},
            {"question_id": 1, "exam_id": 11, "exam_title": "Algebra II"}
        ],
        "skipped": [
            {"question_id": 2, "exam_id": 10, "exam_title": "Algebra I", "reason": "Already exists"}
        ],
        "failed_questions": [
            {"question_id": 3, "reason": "Question not found or archived"}
        ],
        "failed_exams": [
            {"exam_id": 12, "reason": "Exam not found"}
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
    "latest_score": 88.0
  },
  "leaderboard_ranking": {
    "position": 15,
    "total_candidates": 150
  },
  "recent_scores": [
    {
      "exam": "Algebra Screening",
      "score": 88.0,
      "date": "2024-01-20T15:30:00Z",
      "exam_stage": "league"
    }
  ],
  "available_exams": [
    {
      "id": 2,
      "title": "Geometry Screening",
      "description": "Comprehensive geometry exam covering shapes, angles, and spatial reasoning.",
      "open_duration_hours": 12,
      "scheduled_date": "2024-01-25T14:00:00Z",
      "countdown_minutes": 90,
      "question_count": 25,
      "stage": "screening"
    }
  ]
}
```
*Note: If dashboard data is not immediately available (e.g., first load), a `202 Accepted` response will be returned, indicating that the data is being generated asynchronously.*

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
*Note: Similar to the candidate dashboard, a `202 Accepted` response may be returned if data is being generated asynchronously.*

<!-- ### Scoring & Submissions -->

<!-- #### Publish Scores

This endpoint works in hand with the scores displayed in candidates' dashboards. Candidates only see last "published scores" and only see the latest (i.e. exams they recently took) after it's **published** via this endpoint.

**Endpoint:** `POST /publish-scores/`  
**Headers:**
```text
X-Api-Key: <your_api_key>
```
**Required Role:** `admin` or higher  
**Request Body:** empty (just a POST signal is required)
**Response:** `200 OK`
```json
{
  "message": "Scores snapshot generation has been started and will be available shortly.
}
```
*Note: This endpoint will trigger an asynchronous task to publish the scores (to candidates' dashboards).* -->

---

### Leaderboard
The leaderboard system provides detailed performance rankings across different competition stages and levels. It consists of two main views:
<!-- - `LoadLeaderboardView`: For fetching a summary of all available leaderboards or a detailed, paginated view of a specific leaderboard.
- `LoadLeaderboardDetailView`: For fetching the complete performance record of a single candidate in a specific exam. -->

#### 1. Publish Leaderboard
Triggers an asynchronous task to generate and publish a new leaderboard snapshot. This should be done after an exam concludes and all scores are finalized.

**Endpoint:** `POST /api/v1/leaderboard/publish/`
**Required Role:** `admin` or higher
**Request Body:**
This endpoint does not require a request body. It automatically finds all concluded, active exams and generates leaderboards for them.
```json
{}
```
**Response:** `202 Accepted`
```json
{
  "message": "Leaderboard generation has been started and will be available shortly.",
  "task_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef"
}
```

---

#### 2. Load Leaderboard (`LoadLeaderboardView`)
This is the primary endpoint for all frontend leaderboard functionality. It has two modes:

**A. Summary Mode (No Query Parameters)**
Returns a list of all available leaderboards that the current user is permitted to see. Ideal for dynamically populating UI tabs.

**Endpoint:** `GET /api/v1/leaderboard/`
**Required Role:** Any verified user (`candidate` or `staff`)

**Response (200 OK):**
```json
{
  "snapshot_id": 45,
  "published_at": "2024-10-30T14:30:00Z",
  "available_leaderboards": [
    {
      "stage": "screening",
      "level": 1,
      "stage_display": "screening_1",
      "exam_title": "Screening Exam 2024 - Basic Mathematics",
      "total_candidates": 150,
      "average_score": 78.5
    },
    {
      "stage": "league",
      "level": 1,
      "stage_display": "league_1",
      "exam_title": "League Round 1 - General Knowledge",
      "total_candidates": 50,
      "average_score": 85.2
    }
  ]
}
```
*Note: A `screening` candidate would only see leaderboards for the `screening` stage.*

**B. Detail Mode (With Query Parameters)**
Returns the detailed, paginated rankings for a specific leaderboard, identified by `stage` and `level`.

**Endpoint:** `GET /api/v1/leaderboard/?stage=<stage>&level=<level>`
**Required Role:** Any verified user (`candidate` or `staff`)

**Query Parameters:**
- `stage` (string, required): The stage of the leaderboard (e.g., `screening`, `league`).
- `level` (integer, required): The level within the stage (e.g., `1`, `2`).
- `page` (integer, optional): The page number for the `remaining_candidates` list.
- `page_size` (integer, optional): The number of candidates to show per page.

**Response (200 OK):**
This response always includes the `top_three` performers separately and a paginated list of `remaining_candidates`.
```json
{
  "exam_id": 123,
  "exam_title": "Screening Exam 2024 - Basic Mathematics",
  "stage": "screening",
  "level": 1,
  "stage_display": "screening_1",
  "total_candidates": 150,
  "average_score": 78.5,
  "top_three": [
    { "rank": 1, "candidate": { "...": "..." }, "score": 100.0, "percentage": 100.0 },
    { "rank": 2, "candidate": { "...": "..." }, "score": 99.5, "percentage": 99.5 },
    { "rank": 3, "candidate": { "...": "..." }, "score": 99.0, "percentage": 99.0 }
  ],
  "remaining_candidates": [
    { "rank": 4, "candidate": { "...": "..." }, "score": 98.0, "percentage": 98.0 },
    { "rank": 5, "candidate": { "...": "..." }, "score": 98.0, "percentage": 98.0 }
  ],
  "pagination": {
    "count": 147,
    "total_pages": 30,
    "next": "http://localhost:8000/api/v1/leaderboard/?stage=screening&level=1&page=2&page_size=5",
    "previous": null
  }
}
```

**Common Error Responses for `LoadLeaderboardView`:**
- **404 Not Found:** If no published leaderboard exists at all, or if the requested `stage` and `level` do not exist.
  ```json
  { "detail": "No published leaderboard found." }
  // or
  { "detail": "No leaderboard found for league level 99" }
  ```
- **403 Forbidden:** If a user attempts to access a leaderboard they are not permitted to see.
  ```json
  { "detail": "You can only view screening leaderboards." }
  // or
  { "detail": "Candidate must be verified to view the leaderboard." }
  ```

---

#### 3. Load Candidate Detail (`LoadLeaderboardDetailView`)
Retrieves the complete and detailed performance of a single candidate for a specific exam. This is the view used when a user clicks on a candidate's name in the leaderboard.

**Endpoint:** `GET /api/v1/leaderboard/<stage>/<level>/candidate/<candidate_id>/`
**Required Role:**
- `staff` and `league` candidates can view any candidate's detail.
- `screening` candidates can only view their own detail.

**URL Parameters:**
- `stage` (string): The stage of the leaderboard (e.g., `screening`).
- `level` (integer): The level of the leaderboard (e.g., `1`).
- `candidate_id` (uuid): The ID of the candidate whose performance is being requested.

**Response (200 OK):**
This response includes exam information and a detailed breakdown of the candidate's submissions, including every question, their selected answer, the correct answer, and whether they were correct.
```json
{
  "exam_info": {
    "exam_id": 123,
    "exam_title": "Screening Exam 2024 - Basic Mathematics",
    "stage": "screening",
    "level": 1,
    "total_questions": 50
  },
  "candidate_performance": {
    "rank": 4,
    "candidate": {
      "id": 792,
      "user_id": 1004,
      "first_name": "Simon",
      "last_name": "Kawu",
      "email": "simonkawu@yandex.com",
      "school": "University of Ibadan",
      "role": "screening"
    },
    "score": 98.0,
    "percentage": 98.0,
    "submissions": [
      {
        "question_id": 1,
        "question_text": "What is the value of π (pi)?",
        "correct_option": "d",
        "selected_option": "d",
        "is_correct": true,
        "answered_at": "2024-10-30T09:00:15Z"
      },
      {
        "question_id": 3,
        "question_text": "What is the formula for the area of a rectangle?",
        "correct_option": "a",
        "selected_option": "b",
        "is_correct": false,
        "answered_at": "2024-10-30T09:00:45Z"
      }
    ]
  }
}
```

**Common Error Responses for `LoadLeaderboardDetailView`:**
- **404 Not Found:** If the candidate is not found in the specified leaderboard.
  ```json
  { "detail": "Candidate not found in this leaderboard" }
  ```
- **403 Forbidden:** If a `screening` candidate tries to view another candidate's details.
  ```json
  { "detail": "You can only view your own performance." }
  ```


---

### User Verification
User verification is a multi-step process involving email verification, document submission, and admin approval.

#### 1. Get Verification Status
Retrieve the verification status for the authenticated user or for a specific user if you are a superadmin.

**Endpoints:**
- `GET /user/verification/status/` (for self)
- `GET /user/verification/status/{user_id}/` (for managers or higher)

**Headers:**
```text
X-Api-Key: <your_api_key>
```

**Required Role:**
- Any authenticated user for their own status.
- `manager` or higher to check another user's status.

**Responses:**
The API returns a consistent JSON object with a `status` field that indicates the current state of the user's verification.

- **Status: `email_not_verified`**
  ```json
  {
      "status": "email_not_verified",
      "detail": "Email not verified. Verify email for user verification."
  }
  ```

- **Status: `verified`**
  ```json
  {
      "status": "verified",
      "detail": "User is verified."
  }
  ```

- **Status: `pending`**
  ```json
  {
      "status": "pending",
      "detail": "Verification request is pending review.",
      "verification_data": {
          "is_pending": true,
          "is_approved": false,
          "is_rejected": false,
          "created_at": "2025-09-01T10:00:00Z",
          "updated_at": "2025-09-01T10:00:00Z",
          "documents_uploaded": {
              "face_id": true,
              "id_card": true,
              "verification_document": true
          }
      }
  }
  ```

- **Status: `rejected`**
  ```json
  {
      "status": "rejected",
      "detail": "Verification request was rejected. You may resubmit with updated documents."
  }
  ```

- **Status: `not_submitted`**
  ```json
  {
      "status": "not_submitted",
      "detail": "No verification request submitted."
  }
  ```

#### 2. Submit or Update Verification Documents
This endpoint allows users to submit their documents for the first time (`POST`) or update an existing submission (`PATCH`). Resubmitting documents will clear any previous rejection and set the status back to pending.

**Endpoint:** `POST /user/verification/upload/`, `PATCH /user/verification/upload/`
**Required Role:** Any authenticated user
**Headers:**
```text
X-Api-Key: <your_api_key>
Content-Type: multipart/form-data
```

**Form Data:**
- `face_id` (file): Your profile picture (max 2MB, JPG/JPEG/PNG).
- `id_card` (file): A valid identification document (max 2MB, JPG/JPEG/PNG/PDF).
- `verification_document` (file): Additional verification document (max 2MB, PDF/DOC/DOCX/JPG/JPEG/PNG).

**Success Response (`202 Accepted`):**
```json
{
    "detail": "Documents uploaded successfully. Validation is in progress.",
    "verification_data": {
        "status": "pending_validation",
        "has_face_id": true,
        "has_id_card": true,
        "has_verification_document": true
    }
}
```
*Note: Document validation is performed asynchronously. The initial response indicates successful upload and pending validation.*

**Error Responses:**
- `403 Forbidden`: If the user's email is not verified.
- `400 Bad Request`: If the user is already verified or has a pending request (for `POST`), or if file validation fails (e.g., invalid file type, size).

#### 3. Access Verification Documents
Access uploaded documents. The API serves the file content directly from secure storage (AWS S3). Private documents (`id_card`, `verification_document`) are served via signed URLs, ensuring temporary and secure access.

**Endpoints:**
- `GET /user/verification/documents/{file_type}/` (for self)
- `GET /user/verification/documents/{file_type}/{user_id}/` (for managers or higher)

**Headers:**
```text
X-Api-Key: <your_api_key>
```

**Required Role:**
- Any authenticated user for their own documents.
- `manager` or higher to access another user's documents.

**URL Parameters:**
- `file_type` (string): `id_card`, `verification_document`, or `face_id`.
- `user_id` (uuid, optional): The ID of the user whose document to access (required for managers or higher accessing other users' documents).

**Successful Response:**
- The raw file content (e.g., an image or PDF) with the correct `Content-Type` header.

**Error Responses:**
- `404 Not Found`: If the file does not exist or has not been uploaded.
- `403 Forbidden`: If you do not have permission to access the document.
- `502 Bad Gateway`: If there is an issue retrieving the file from storage (e.g., S3 error).

#### 4. List All Verification Requests (Admin)
Retrieve a paginated list of all user verification submissions for administrative review.

**Endpoint:** `GET /user/verification/list/`
**Headers:**
```text
X-Api-Key: <your_api_key>
```

**Required Role:** `manager` or higher

**Response:** `200 OK`
```json
{
  "count": 10,
  "total_pages": 1,
  "next": null,
  "previous": null,
  "results": [
    {
        "user_id": "4ecxxxxx-8f43-xxxx-xxxx-xxxxxxxxxx",
        "full_name": "John Doe",
        "email": "john@example.com",
        "is_pending": true,
        "is_approved": false,
        "is_rejected": false,
        "has_face_id": true,
        "has_id_card": true,
        "has_verification_document": false,
        "created_at": "2025-08-30T16:33:19Z"
    }
  ]
}
```

#### 5. Approve or Reject a Verification Request (Admin)
Allows a `manager` or higher to approve or reject a user's verification submission. This action is final and notifies the user via email.

**Endpoint:** `POST /user/verification/action/{user_id}/`
**Headers:**
```text
Content-Type: application/json
X-Api-Key: <your_api_key>
```

**Required Role:** `manager` or higher

**URL Parameters:**
- `user_id` (uuid): The ID of the user whose verification is being actioned.

**Request Body:**
To approve a user:
```json
{
    "is_approved": true
}
```
To reject a user:
```json
{
    "is_rejected": true
}
```

**Success Response (`200 OK`):**
```json
{
    "detail": "User verified successfully."
}
```
*or*
```json
{
    "detail": "User verification rejected."
}
```
*Note: An email notification is sent to the user upon approval or rejection.*

---

### Account Management
The account management endpoints allow users to view and update their own profile information. Superadmins have the ability to manage other users' accounts.

#### Get Account Details (Self)
**Endpoint:** `GET /account-management/`
**Headers:**
```text
X-Api-Key: <your_api_key>
```
**Required Role:** Any authenticated user

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
      "phone": "+23490xxxxxxxx",
      "date_joined": "2024-01-15T10:30:00Z"
    },
    "school": "Mathematics High School",
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
*Note: The structure of the `profile` object will vary based on whether the user is a candidate or staff.*

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
*Note: The structure of the `profile` object will vary based on whether the user is a candidate or staff.*

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
*Note: You can update `user` fields, `profile` fields, or both. The `profile` fields will depend on whether the user is a candidate or staff.*

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
The broadcast system allows authorized staff to send targeted communications to candidates. Broadcasts are sent asynchronously, and their status can be tracked.

#### List Broadcasts
**Endpoint:** `GET /broadcasts/`  
**Headers:**
```text
X-Api-Key: <your_api_key>
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
        "user": { "email": "manager@example.com", "first_name": "Manager", "last_name": "User" },
        "occupation": "System Manager", "role": "manager"
      },
      "created_at": "2025-09-20T10:00:00Z",
      "mediums": ["email", "platform"],
      "target_roles": ["league", "final"]
    }
  ]
}
```

#### Create Broadcast
**Endpoint:** `POST /broadcasts/`  
**Headers:**
```text
X-Api-Key: <your_api_key>
```
**Required Role:** `manager` or higher  
**Request Body:**
```json
{
  "subject": "New Exam Available",
  "message": "The final stage exam is now open. Good luck!",
  "mediums": ["email", "platform"],
  "target_roles": ["final"]
}
```
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
    "target_roles": ["final"],
    "logs": []
}
```
*Note: Creating a broadcast triggers an asynchronous task. The response includes the task_id for tracking. If platform is a medium, a real-time notification will be pushed to connected clients via WebSockets.*

#### Get Broadcast Details
**Endpoint:** `GET /broadcasts/{broadcast_id}/`  
**Required Role:** `manager` or higher
*Note: The response for this endpoint is cached for performance. The cache is invalidated when the broadcast sending task completes.*
**Response:** `200 OK` (Returns the detailed broadcast object, including the status and logs of sending attempts)

---

## Advanced Topics

### Query Parameters
#### Common Parameters
| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `page` | integer | Page number for pagination | `?page=2` |
| `limit` | integer | Items per page (max: 100) | `?limit=25` |
| `search` | string | Search across relevant fields (e.g., name, email, title) | `?search=john` |
| `ordering` | string | Sort results (`field` or `-field` for descending) | `?ordering=-created_at` |

#### Filtering Parameters
| Endpoint | Parameter | Type | Description |
|----------|-----------|------|-------------|
| `/candidates/` | `role` | string | Filter by candidate role (`screening`, `league`, `final`, `winner`) |
| `/candidates/` | `school` | string | Filter by school name |
| `/candidates/` | `verified` | boolean | Filter by verification status (`true` or `false`) |
| `/staff/` | `role` | string | Filter by staff role (`volunteer`, `moderator` or higher) |
| `/staff/` | `occupation` | string | Filter by occupation |
| `/exams/` | `stage` | string | Filter by exam stage (`screening`, `league`) |
| `/exams/` | `active` | boolean | Filter by active status (`true` or `false`) |
| `/questions/` | `difficulty` | string | Filter by question difficulty (`easy`, `moderate`, `hard`) |
| `/questions/` | `created_by` | uuid | Filter by the UUID of the staff member who created the question |
| `/user/verification/list/` | `is_pending` | boolean | Filter by pending verification status |
| `/user/verification/list/` | `is_approved` | boolean | Filter by verified status |
| `/user/verification/list/` | `is_rejected` | boolean | Filter by rejected status |

#### Date Filtering
Use ISO 8601 format for date parameters:

| Parameter | Format | Example |
|-----------|--------|---------|
| `date_from` | YYYY-MM-DD | `?date_from=2024-01-01` |
| `date_to` | YYYY-MM-DD | `?date_to=2024-12-31` |
| `created_after` | YYYY-MM-DDTHH:MM:SS | `?created_after=2024-01-01T10:00:00` |
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

| Code | Status | Description |
|------|-------------------------|-----------------------------------------------------------------------------|
| 200 | OK | Request successful. |
| 201 | Created | Resource created successfully. |
| 202 | Accepted | Request accepted for processing, but the processing is not yet complete (e.g., asynchronous task). |
| 204 | No Content | Resource deleted successfully or action completed with no content to return. |
| 400 | Bad Request | Invalid input, such as a malformed request body or invalid parameters. |
| 401 | Unauthorized | Authentication credentials were not provided or were invalid. |
| 403 | Forbidden | You do not have permission to perform this action (e.g., insufficient role, unverified account, feature disabled). |
| 404 | Not Found | The requested resource could not be found. |
| 429 | Too Many Requests | You have exceeded the rate limit. |
| 500 | Internal Server Error | An unexpected error occurred on the server. |
| 502 | Bad Gateway | The server received an invalid response from an upstream server (e.g., S3 error). |

### Common Error Codes

| Code | Description |
|---------------------------|-----------------------------------------------------------------------------|
| `authentication_failed` | Incorrect authentication credentials. |
| `not_authenticated` | Authentication credentials were not provided. |
| `permission_denied` | You do not have permission to perform this action. |
| `not_found` | The requested resource could not be found. |
| `invalid` | Invalid input (e.g., validation errors in request body). |
| `invalid_token` | Token is invalid or expired. |
| `rate_limit_exceeded` | You have exceeded the rate limit. |
| `no_recipients_found` | A broadcast operation found no recipients for the specified target. |
| `invalid_medium` | The specified broadcast medium is invalid or not implemented. |
| `registration_closed` | Registration for this type of user is currently disabled by a feature flag. |
| `email_not_verified` | User's email address has not been verified. |
| `already_verified` | User is already verified and cannot resubmit verification documents. |
| `pending_verification` | User has a pending verification request and cannot submit a new one (for POST). |
| `unverified_candidate` | Candidate must be verified to perform this action (e.g., take an exam, assign role). |
| `unverified_staff` | Staff member must be verified to perform this action. |
| `exam_not_open` | The exam is not currently open for submissions. |
| `exam_not_eligible` | The candidate's role does not match the exam stage. |
| `exam_already_submitted` | The candidate has already submitted answers for this exam. |
| `invalid_file_type` | The uploaded file has an unsupported extension. |
| `file_size_exceeded` | The uploaded file exceeds the maximum allowed size. |
| `leaderboard_hidden` | The leaderboard is currently not visible to the public. |
| `leaderboard_not_published` | The leaderboard has not been published yet. |
| `account_already_authenticated` | An authenticated user attempted to register a new account. |
| `invalid_otp` | The provided One-Time Password is invalid or expired. |
| `passwords_do_not_match` | New password and confirmation password do not match. |
| `password_validation_failed` | The new password does not meet security requirements. |

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
*Note: The exact `detail` message and `code` might vary slightly based on the throttling implementation.*

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

- **2025-10-30**
  - **User/profile data**
    - Profile object (e.g. candiate) `is_verified` field is renamed to `is_user_verified`.
    - User object (e.g. candidate.user) now contains `is_email_verified` field accros endpoints.
  - **User verification**
    - `is_verified` is now renamed to `is_approved`. E.g. Manager approves user verification: `"is_approved": true` | `"is_rejected": true`

- **2025-10-29**
  - **Leaderboard**
    - *Breaking Change:* Modified the leaderboard generation and retrieval process.
        - `POST /publish-leaderboard/`: Now requires an `exam_id` in the request body to specify which exam's leaderboard to generate and publish. The permission remains `admin` and higher.
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

_Last Updated: October 2025_