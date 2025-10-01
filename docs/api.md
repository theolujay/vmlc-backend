# VMLC API Documentation

## Table of Contents
- [Overview](#overview)
- [Getting Started](#getting-started)
  - [Base URL](#base-url)
  - [Authentication](#authentication)
  - [User Roles & Permissions](#user-roles--permissions)
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

`base_url = https://vmlc-api.onrender.com/v1/`

All endpoints are relative to this base URL. A discoverable list of endpoints is available at the [root](#root-endpoint) endpoint.

---

### Authentication
The API uses `X-Api-Key` for general authentication. The API key should be provided in the `X-Api-Key` header:

`X-Api-Key: <your_api_key>`

For endpoints that require user-specific permissions, a JWT access token must also be provided in the `Authorization` header. This is typically required for actions performed by authenticated users, such as accessing their profile, taking an exam, or for staff members managing resources. Some endpoints may require both `X-Api-Key` and `Authorization: Bearer <access-token>`.

`Authorization: Bearer <access-token>`


This is typically required for actions performed by authenticated users, such as accessing their profile, taking an exam, or for staff members managing resources.

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
  "root": "https://vmlc-api.onrender.com/v1/root/",
  "authentication": {
    "login": "https://vmlc-api.onrender.com/v1/auth/login/",
    "logout": "https://vmlc-api.onrender.com/v1/auth/logout/",
    "token_refresh": "https://vmlc-api.onrender.com/v1/auth/token/refresh/"
  },
  // ... other endpoints ...
}
```

---

## User Roles & Permissions
The VMLC API implements a robust Role-Based Access Control (RBAC) system, ensuring that users can only access resources and perform actions relevant to their assigned roles.

### Candidate Roles
| Role | Description | Permissions |
|------|-------------|-------------|
| `screening` | Default role for new candidates. | Access to candidate dashboard, participate in screening exams, view own profile and verification status. |
| `league` | Candidates who have progressed past the screening stage (staff-assigned). | All `screening` permissions, plus access to league exams and leaderboard. |
| `final` | Top performers from the league stage (staff-assigned). | All `league` permissions, plus access to (although not on the portal) final stage exams. |
| `winner` | The ultimate competition winner (staff-assigned). | Ceremonial role with all candidate permissions. |

### Staff Roles
The API now uses a hierarchical role system. Users with a higher role inherit all permissions from the roles below them.

| Role (Hierarchy) | Description | Key Permissions |
|------------------|-------------|-----------------|
| `volunteer` | Basic staff member. | Restricted permissions. Can apply for user verification. |
| `sponsor` | Vanity role. | Unused. |
| `moderator` | Responsible for basic moderation. | All `volunteer` permissions, plus ability to view candidates/staff lists and manage questions (CRUD). |
| `admin` | Operations administrator. | All `moderator` permissions, plus full management of candidates (CRUD, role assignment), exams (CRUD), scores (manual submission, publishing), and leaderboard (publishing). |
| `manager` | Senior administrator. | All `admin` permissions, plus ability to manage staff members (CRUD, role assignment) and access to user verification process and documents. Cannot assign `manager` or `superadmin` roles. |
| `superadmin` | Platform administrator with full control. | All `manager` permissions, plus ability to assign any staff role (excluding `superadmin`). |

### Role Progression
- **Candidates**: `screening` → `league` → `final` → `winner` (progression is managed by staff with `admin` role or higher)
- **Staff**: Roles are assigned by a `manager` or `superadmin`.

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
  "next": "https://vmlc-api.onrender.com/v1/candidates/?page=2",
  "previous": null,
  "results": [
    {
      "user": {
        "email": "john@example.com",
        "first_name": "John",
        "last_name": "Doe",
        "phone": "+23490xxxxxxxx"
      },
      "school": "Mathematics High School",
      "role": "league",
      "is_verified": true
    }
  ]
}
```

#### Get Candidate Details
**Endpoint:** `GET /candidates/{candidate_id}/`
**Headers:**
```text
X-Api-Key: <your_api_key>
```
**Required Role:** `moderator` or higher

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
  "profile_photo": "https://vmlc.s3.amazonaws.com/profile_photos/john_doe.jpg",
  "role": "league",
  "is_active": true,
  "is_verified": true,
  "id_card": "https://vmlc.s3.amazonaws.com/id_cards/john_doe_id.pdf?AWSAccessKeyId=...",
  "verification_document": "https://vmlc.s3.amazonaws.com/verification_docs/john_doe_doc.pdf?AWSAccessKeyId=...",
  "date_created": "2024-01-15T10:30:00Z",
  "date_updated": "2024-01-20T11:00:00Z",
  "scores": {
    "total_score": 380.0,
    "average_score": 95.0,
    "scores": [
      {
        "exam_id": 1,
        "exam_title": "Algebra Screening",
        "score": 88.0,
        "date_recorded": "2024-01-20T15:30:00Z",
        "submitted_by": "Admin User",
        "auto_score": true
      }
    ]
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
        "first_name": "John",
        "last_name": "Doe",
        "phone": "+23490xxxxxxxx",
        "date_joined": "2024-01-15T10:30:00Z"
      },
      "school": "Mathematics High School",
      "role": "league",
      "is_verified": true
    },
    "exam": {
      "id": 1,
      "title": "Algebra Screening Exam",
      "stage": "screening",
      "question_count": 20,
      "date_created": "2024-01-10T09:00:00Z"
    },
    "score": 88.0,
    "date_recorded": "2024-01-20T15:30:00Z"
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
    "first_name": "Jane",
    "last_name": "Smith",
    "phone": "+23490xxxxxxxx",
    "date_joined": "2024-01-01T08:00:00Z"
  },
  "occupation": "Mathematics Teacher",
  "profile_photo": "https://vmlc.s3.amazonaws.com/profile_photos/jane_smith.jpg",
  "role": "moderator",
  "is_active": true,
  "is_verified": true,
  "id_card": "https://vmlc.s3.amazonaws.com/id_cards/jane_smith_id.pdf?AWSAccessKeyId=...",
  "verification_document": "https://vmlc.s3.amazonaws.com/verification_docs/jane_smith_doc.pdf?AWSAccessKeyId=...",
  "date_created": "2024-01-01T08:00:00Z",
  "date_updated": "2024-01-05T09:00:00Z"
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
  "count": 25,
  "next": "https://vmlc-api.onrender.com/v1/exams/?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "title": "Algebra Screening Exam",
      "stage": "screening",
      "question_count": 20,
      "date_created": "2024-01-10T09:00:00Z"
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
  "exam_date": "2025-10-01T10:00:00Z",
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
  "exam_date": "2025-10-01T10:00:00Z",
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
  "date_created": "2025-09-18T12:00:00Z"
}
```

#### Get Exam Details
**Endpoint:** `GET /exams/{exam_id}/`  
**Headers:**
```text
X-Api-Key: <your_api_key>
```
**Required Role:** 'admin' or higher  
**Response:** `200 OK`
```json
{
  "id": 1,
  "title": "Algebra Screening Exam",
  "stage": "screening",
  "description": "Comprehensive algebra exam covering linear equations, polynomials, and systems.",
  "exam_date": "2024-01-20T15:00:00Z",
  "countdown_minutes": 90,
  "open_duration_hours": 24,
  "is_active": true,
  "questions": [1, 4, 8],
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
  "average_score": 78.5,
  "date_created": "2024-01-10T09:00:00Z"
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
    "date_created": "2024-01-10T09:00:00Z",
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
    "submitted_by": null,
    "date_recorded": "2024-01-20T15:30:00Z"
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
**Required Role:** Authenticated `candidate` with `is_verified=true` and `role` matching `exam.stage`.  
**Response:** `200 OK`
```json
{
  "id": 1,
  "title": "Algebra Screening Exam",
  "stage": "screening",
  "description": "Comprehensive algebra exam covering linear equations, polynomials, and systems.",
  "open_duration_hours": 12,
  "exam_date": "2024-01-20T15:00:00Z",
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
- `difficulty` (string): Filter by difficulty (`easy`, `medium`, `hard`)
- `search` (string): Search question text
- `created_by` (uuid): Filter by the UUID of the staff member who created the question

**Response:** `200 OK`
```json
{
  "count": 100,
  "results": [
    {
      "id": 1,
      "text": "What is 5 × 5?",
      "difficulty": "easy",
      "date_created": "2024-01-10T09:00:00Z"
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
  "date_created": "2025-09-18T12:30:00Z",
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
  "difficulty": "easy",
  "date_created": "2024-01-10T09:00:00Z",
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
  "difficulty": "medium"
}
```
**Response:** `200 OK` (Returns updated question details)

#### Delete Question
**Endpoint:** `DELETE /questions/{question_id}/`  
**Required Role:** `moderator` or higher  
**Response:** `204 No Content`
*Note: Questions are soft-deleted by setting `is_active` to `False`.*

---

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
    "is_verified": false,
    "date_joined": "2024-01-15T10:30:00Z",
    "profile_photo": "https://vmlc.s3.amazonaws.com/candidate_profile_photos/8.jpg"
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
      "exam_date": "2024-01-25T14:00:00Z",
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
    "is_verified": true,
    "date_joined": "2024-01-01T08:00:00Z",
    "profile_photo": "https://vmlc.s3.amazonaws.com/staff_profile_photos/7.jpg"
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
      "medium": { "count": 200 },
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
      "exam_date": "2024-01-25T14:00:00Z",
      "is_active": true,
      "stage": "screening",
      "question_count": 25,
      "countdown_minutes": 90
    }
  ]
}
```
*Note: Similar to the candidate dashboard, a `202 Accepted` response may be returned if data is being generated asynchronously.*

---

### Leaderboard
The leaderboard displays candidate rankings and can be dynamically controlled by staff.

#### Toggle Leaderboard Visibility
Allows 'admin' or higher to enable or disable the public visibility of the leaderboard.

**Endpoint:** `POST /toggle-leaderboard/`  
**Headers:**
```text
X-Api-Key: <your_api_key>
```
**Required Role:** `admin` or higher  
**Request Body:**
```json
{
  "open": true
}
```
*Note: Use `true` to make the leaderboard visible, `false` to hide it.*

**Response:** `200 OK`
```json
{
  "message": "Leaderboard is now visible."
}
```
*or*
```json
{
  "message": "Leaderboard is now hidden."
}
```

#### Publish Leaderboard
Triggers an asynchronous task to generate and publish the latest leaderboard snapshot.

**Endpoint:** `POST /publish-leaderboard/`  
**Headers:**
```text
X-Api-Key: <your_api_key>
```
**Required Role:** `admin` or higher  
**Response:** `202 Accepted`
```json
{
  "message": "Leaderboard generation has been started and will be available shortly."
}
```

#### Load Leaderboard
Retrieves the most recently published leaderboard snapshot. The leaderboard's visibility is controlled by a feature flag.

**Endpoint:** `GET /load-leaderboard/`  
**Headers:**
```text
X-Api-Key: <your_api_key>
```
**Required Role:** `league` candidates and above, all staff  

**Query Parameters:**
- `limit` (integer): Number of results (default: 50, max: 100)
- `offset` (integer): Starting position

**Response:** `200 OK`
```json
{
  "published_at": "2024-01-20T18:00:00Z",
  "total_candidates": 150,
  "results": [
    {
      "rank": 1,
      "candidate": {
        "user": {
          "email": "alice@example.com",
          "first_name": "Alice",
          "last_name": "Johnson"
        },
        "school": "Riverdale High"
      },
      "total_score": 98.0
    }
  ]
}
```
*Note: A `403 Forbidden` will be returned if the leaderboard is currently hidden.*

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
          "is_verified": false,
          "is_rejected": false,
          "date_created": "2025-09-01T10:00:00Z",
          "date_updated": "2025-09-01T10:00:00Z",
          "documents_uploaded": {
              "profile_photo": true,
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
- `profile_photo` (file): Your profile picture (max 2MB, JPG/JPEG/PNG).
- `id_card` (file): A valid identification document (max 2MB, JPG/JPEG/PNG/PDF).
- `verification_document` (file): Additional verification document (max 2MB, PDF/DOC/DOCX/JPG/JPEG/PNG).

**Success Response (`202 Accepted`):**
```json
{
    "detail": "Documents uploaded successfully. Validation is in progress.",
    "verification_data": {
        "status": "pending_validation",
        "has_profile_photo": true,
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
- `file_type` (string): `id_card`, `verification_document`, or `profile_photo`.
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
  "next": null,
  "previous": null,
  "results": [
    {
        "user_id": "4ecxxxxx-8f43-xxxx-xxxx-xxxxxxxxxx",
        "user_name": "John Doe",
        "email": "john@example.com",
        "is_pending": true,
        "is_verified": false,
        "is_rejected": false,
        "has_profile_photo": true,
        "has_id_card": true,
        "has_verification_document": false,
        "date_created": "2025-08-30T16:33:19Z"
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
    "is_verified": true
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
      "first_name": "John",
      "last_name": "Doe",
      "phone": "+23490xxxxxxxx",
      "date_joined": "2024-01-15T10:30:00Z"
    },
    "school": "Mathematics High School",
    "profile_photo": "https://vmlc.s3.amazonaws.com/profile_photos/john_doe.jpg",
    "role": "league",
    "is_active": true,
    "is_verified": true,
    "id_card": "https://vmlc.s3.amazonaws.com/id_cards/john_doe_id.pdf?AWSAccessKeyId=...",
    "verification_document": "https://vmlc.s3.amazonaws.com/verification_docs/john_doe_doc.pdf?AWSAccessKeyId=...",
    "date_created": "2024-01-15T10:30:00Z",
    "date_updated": "2024-01-20T11:00:00Z",
    "scores": {
      "total_score": 380.0,
      "average_score": 95.0,
      "scores": [
        {
          "exam_id": 1,
          "exam_title": "Algebra Screening",
          "score": 88.0,
          "date_recorded": "2024-01-20T15:30:00Z",
          "submitted_by": "Admin User",
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
      "first_name": "Jane",
      "last_name": "Smith",
      "phone": "+23490xxxxxxxx",
      "date_joined": "2024-01-01T08:00:00Z"
    },
    "occupation": "Mathematics Teacher",
    "profile_photo": "https://vmlc.s3.amazonaws.com/profile_photos/jane_smith.jpg",
    "role": "moderator",
    "is_active": true,
    "is_verified": true,
    "id_card": "https://vmlc.s3.amazonaws.com/id_cards/jane_smith_id.pdf?AWSAccessKeyId=...",
    "verification_document": "https://vmlc.s3.amazonaws.com/verification_docs/jane_smith_doc.pdf?AWSAccessKeyId=...",
    "date_created": "2024-01-01T08:00:00Z",
    "date_updated": "2024-01-05T09:00:00Z"
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
      "first_name": "Jonathan",
      "last_name": "Doe",
      "phone": "+23490xxxxxxxx",
      "date_joined": "2024-01-15T10:30:00Z"
    },
    "school": "New High School",
    "profile_photo": "https://vmlc.s3.amazonaws.com/profile_photos/john_doe.jpg",
    "role": "league",
    "is_active": true,
    "is_verified": true,
    "id_card": "https://vmlc.s3.amazonaws.com/id_cards/john_doe_id.pdf?AWSAccessKeyId=...",
    "verification_document": "https://vmlc.s3.amazonaws.com/verification_docs/john_doe_doc.pdf?AWSAccessKeyId=...",
    "date_created": "2024-01-15T10:30:00Z",
    "date_updated": "2024-01-20T11:00:00Z",
    "scores": {
      "total_score": 380.0,
      "average_score": 95.0,
      "scores": [
        {
          "exam_id": 1,
          "exam_title": "Algebra Screening",
          "score": 88.0,
          "date_recorded": "2024-01-20T15:30:00Z",
          "submitted_by": "Admin User",
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
| `ordering` | string | Sort results (`field` or `-field` for descending) | `?ordering=-date_created` |

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
| `/questions/` | `difficulty` | string | Filter by question difficulty (`easy`, `medium`, `hard`) |
| `/questions/` | `created_by` | uuid | Filter by the UUID of the staff member who created the question |
| `/user/verification/list/` | `is_pending` | boolean | Filter by pending verification status |
| `/user/verification/list/` | `is_verified` | boolean | Filter by verified status |
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
- **Swagger UI**: `https://vmlc-api.onrender.com/v1/docs/swagger/`
- **ReDoc**: `https://vmlc-api.onrender.com/v1/docs/redoc/`

---

## Support
For technical support, API key requests, or questions:
- **Email:** `theolujay@gmail.com`
- **Discord:** `@olujay`
- **X:** `@theolujay`
- **Response Time:** Within 48 hours for support requests.


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
- **Base URL** is now `https://vmlc-api.onrender.com/v1/`
- **Custom Exception Handling**: Introduced custom exception classes for more specific and consistent error responses.

### Version 0.1.0
- Initial API release
- Complete user management system
- Exam administration features
- Leaderboard functionality
- Role-based access control

_Last Updated: October 2025_
