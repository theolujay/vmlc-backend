# VMLC API Documentation

## Table of Contents
- [Overview](#overview)
- [Base URL](#base-url)
- [Authentication](#authentication)
- [User Roles & Permissions](#user-roles--permissions)
- [API Endpoints](#api-endpoints)
  - [Registration & System Controls](#registration--system-controls)
  - [Email Verification](#email-verification)
  - [Candidate Management](#candidate-management)
  - [Staff Management](#staff-management)
  - [Exam Management](#exam-management)
  - [Question Management](#question-management)
  - [Dashboard](#dashboard)
  - [Leaderboard](#leaderboard)
  - [User Verification](#user-verification)
- [Query Parameters](#query-parameters)
- [Error Handling](#error-handling)
- [Rate Limiting](#rate-limiting)
- [Versioning](#versioning)
- [Interactive Documentation](#interactive-documentation)
- [Support](#support)
- [Changelog](#changelog)

---

## Overview
The VMLC API provides an integrated backend service for the Verboheit Mathematics League Competition, handling registration, exam administration, scoring, and leaderboard functionality with role-based access control.

### Key Features
- **User Management**: Candidate and staff registration with role-based access control
- **Exam System**: Create, manage, and administer timed exams with automatic scoring
- **Leaderboards**: Real-time ranking system based on candidate performance
- **Dashboard**: Personalized views for candidates and staff members
- **Security**: JWT-based authentication with API key protection

### API Characteristics
- **Format**: JSON-only API
- **Authentication**: JWT Bearer tokens for most endpoints and API key for specific endpoints
- **Pagination**: Page-based pagination
- **Rate Limiting**: 1000 requests per day for authenticated users, 60 per day for anonymous users
- **CORS**: Enabled for web applications

---

## Base URL
```
https://vmlc-api.onrender.com/api/v1/
```
All endpoints are relative to this base URL. List of endpoints available at `root/` endpoint.

---

## Authentication
The API uses JWT (JSON Web Tokens) for authentication with two-tier security:

### API Key Authentication (Public Endpoints)
Required for registration and login endpoints:
```text
Authorization: Api-Key <your_api_key>
```

### Bearer Token Authentication (Protected Endpoints)
Required for other authenticated endpoints:
```text
Authorization: Bearer <access_token>
```

### Login Flow
**Endpoint:** `POST /auth/login/`

**Headers:**
```text
Authorization: Api-Key <your_api_key>
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
  "user": {
    "id": "4ecxxxxx-8f43-xxxx-xxxx-xxxxxxxxxx",
    "email": "john@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "phone": "+23490xxxxxxxx",
    "date_joined": "2024-01-15T10:30:00Z"
  }
}
```

### Token Management
#### Refresh Token
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

#### Logout
**Endpoint:** `POST /auth/logout/`

**Request Body:**
```json
{
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

#### Password Change
**Request Password Change OTP**
**Endpoint:** `POST /auth/password-change/request/`

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

**Confirm User for Password Change with OTP**
**Endpoint:** `POST /auth/password-change/confirm-otp/`

**Request Body:**
```json
{
  "email": "user@example.com",
  "otp": "123456"
}**Response:** `200 OK`
```json
{
  "message": "OTP verified. User confirmed for password change. Proceed to change password."
}
```

**Change Password with OTP**
**Endpoint:** `POST /auth/password-change/`

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

**Resend Password Change OTP**
**Endpoint:** `POST /auth/password-change/resend-otp/`

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

## User Roles & Permissions
### Candidate Roles
| Role | Description | Permissions |
|------|-------------|-------------|
| `screening` | Default role for new candidates | Dashboard access, screening exams, own profile |
| `league` | Advanced candidates (staff-assigned) | League exams + leaderboards |
| `final` | Top performers (staff-assigned) | All league permissions + final stage access |
| `winner` | Competition winner (staff-assigned) | Ceremonial role with all permissions |

### Staff Roles
| Role | Description | Permissions |
|------|-------------|-------------|
| `volunteer` | Basic staff member | User verification |
| `sponsor` | Competition sponsor | Vanity role |
| `moderator` | Content moderator | View candidates/staff, manage questions |
| `admin` | Operations administrator | Full management except staff roles |
| `superadmin` | Platform administrator | All permissions including staff management |

### Role Progression
- **Candidates**: `screening` → `league` → `final` → `winner`
- **Staff**: `volunteer` → `moderator` → `admin` → `superadmin`

---

## API Endpoints
### Registration & System Controls
<!-- #### Toggle Registration Status
**Candidate Registration Toggle**
**Endpoint:** `POST /toggle-candidate-registration/`  
**Required Role:** `admin`, `superadmin`  
**Request Body:**
```json
{
  "open": false
}
```

**Response:** `200 OK`
```json
{
  "message": "Candidate registration is now closed"
}
```

**Staff Registration Toggle**  
**Endpoint:** `POST /toggle-staff-registration/`  
**Required Role:** `superadmin`  
**Request Body:** Same as candidate toggle -->

#### Register New Users
**Candidate Registration**  
**Endpoint:** `POST /register/candidate/`  
**Headers:** `Authorization: Api-Key <your_api_key>`  
**Request Body:**
```json
{
  "user": {
    "email": "john@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "phone": "+23490xxxxxxxx"
  },
  "password": "secure_password_123",
  "password2": "secure_password_123",
  "school": "Mathematics High School"
}
```

**Response:** `201 Created`
```json
{
  "message": "Registration successful"
}
```

**Staff Registration**  
**Endpoint:** `POST /register/staff/`  
**Headers:** `Authorization: Api-Key <your_api_key>`  
**Request Body:**
```json
{
  "user": {
    "email": "jane@example.com",
    "first_name": "Jane",
    "last_name": "Smith",
    "phone": "+23490xxxxxxxx"
  },
  "password": "secure_password_123",
  "password2": "secure_password_123",
  "occupation": "Mathematics Teacher"
}
```

### Email Verification
#### Verify Email with OTP
**Endpoint:** `POST /verify-email-otp/`  
**Headers:** `Authorization: Api-Key <your_api_key>`  
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

### Candidate Management
#### List Candidates
**Endpoint:** `GET /candidates/`  
**Required Role:** `moderator`, `admin`, `superadmin`  

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
  "next": "https://verboheit-backend.onrender.com/api/v1/candidates/?page=2",
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

#### Role Management
**Assign Role**  
**Endpoint:** `POST /candidates/{candidate_id}/roles/assign/`  
**Required Role:** `admin`, `superadmin`  
**Request Body:**
```json
{
  "role": "league"
}
```

#### Scores
**Get Candidate Scores**  
**Endpoint:** `GET /candidates/{candidate_id}/scores/`  
**Required Role:** `admin`, `superadmin`  
**Response:** `200 OK`
```json
{
  "user": {
    "id": 123,
    "username": "john_doe",
    "first_name": "John",
    "last_name": "Doe"
  },
  "school": "Mathematics High School",
  "role": "league",
  "latest_score": 95.5,
  "total_score": 380.0,
  "average_score": 95.0,
  "scores": [
    {
      "exam_id": 1,
      "exam_title": "Algebra Screening",
      "score": 88.0,
      "date_recorded": "2024-01-20T15:30:00Z",
      "submitted_by": {
        "id": 10,
        "name": "Admin User"
      }
    }
  ]
}
```

**Publish Scores (Staff only)**  
**Endpoint:** `POST /publish-scores/`  
**Required Role:** `admin`, `superadmin`  
**Response:** `201 Created`
```json
{
  "message": "Scores published successfully!",
  "published_at": "2025-08-02T12:45:06.058245Z"
}
```

**Get Exam History**  
**Endpoint:** `GET /candidates/{candidate_id}/exam-history/`  
**Required Role:** `admin`, `superadmin`  
**Response:** `200 OK`
```json
[
  {
    "exam": "Algebra Screening",
    "score": 88.0,
    "date": "2024-01-20T15:30:00Z",
    "duration_minutes": 87
  }
]
```

### Staff Management
#### List Staff
**Endpoint:** `GET /staff/`  
**Required Role:** `moderator`, `admin`, `superadmin`  

**Query Parameters:**
- `page` (integer): Page number
- `search` (string): Search by name or email
- `role` (string): Filter by staff role
- `occupation` (string): Filter by occupation

#### Assign Staff Role
**Endpoint:** `POST /staff/{staff_id}/roles/assign/`  
**Required Role:** `superadmin`  
**Request Body:**
```json
{
  "role": "admin"
}
```

### Exam Management
#### List Exams
**Endpoint:** `GET /exams/`  
**Required Role:** `admin`, `superadmin`  

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
  "next": "https://verboheit-backend.onrender.com/api/v1/exams/?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "title": "Algebra Screening Exam",
      "stage": "screening",
      "exam_date": "2024-01-20T15:00:00Z",
      "question_count": 20,
      "is_active": true,
      "average_score": 78.5,
      "participants_count": 45,
      "date_created": "2024-01-10T09:00:00Z"
    }
  ]
}
```

#### Exam Details
**Get Exam Information**  
**Endpoint:** `GET /exams/{exam_id}/`  
**Required Role:** `admin` or `superadmin`  
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
      "id": 10,
      "username": "admin_user",
      "first_name": "Admin",
      "last_name": "User"
    }
  },
  "average_score": 78.5,
  "participants_count": 45,
  "date_created": "2024-01-10T09:00:00Z"
}
```

#### Exam Interaction
**View Exam Questions**  
**Endpoint:** `GET /exams/{exam_id}/questions/`  
**Required Role:** `admin` or `superadmin`  
**Response:** `200 OK`
```json
{
  "count": 20,
  "results": [
    {
      "id": 1,
      "text": "What is 5 × 5?",
      "option_a": "20",
      "option_b": "25",
      "option_c": "205",
      "option_d": "250",
      "difficulty": "easy"
    }
  ]
}
```

**Get Exam Results**

Retrieves a list of all exams a specific candidate has taken, including their scores and the date of submission. This provides a chronological record of a candidate's performance.

- **Endpoint:** `GET /candidates/{candidate_id}/exam-history/`

- **Required Role:** `admin` or `superadmin`

- **Response:** `200 OK`
```json
[
  {
    "exam": {
      "id": 1,
      "title": "Algebra Screening",
      "stage": "screening"
    },
    "score": 88.0,
    "date_recorded": "2024-01-20T15:30:00Z",
    "auto_score": true
  },
  {
    "exam": {
      "id": 3,
      "title": "League Week 1",
      "stage": "league"
    },
    "score": 92.5,
    "date_recorded": "2024-02-05T11:20:15Z",
    "auto_score": false
  }
]
```

**Candidate Take Exam**  
**Endpoint:** `POST /exams/{exam_id}/take-exam/`  
**Required Role:** Candidate with appropriate stage access  
**Response:** `200 OK`
```json
{
  "id": 1,
  "title": "Algebra Screening Exam",
  "stage": "screening",
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
  ],
  "start_time": "2024-01-20T15:00:00Z"
}
```

**Submit Exam Answers**  
**Endpoint:** `POST /exams/{exam_id}/submit-exam-answers/`  
**Required Role:** Candidate taking the exam  
**Request Body:**
```json
{
  "answers": [
    {
      "question": 1,
      "selected_option": "B"
    }
  ]
}
```

**Response:** `200 OK`
```json
{
  "message": "Exam submitted successfully",
  "score": 85.0,
  "correct_answers": 17,
  "total_questions": 20,
  "submission_time": "2024-01-20T16:27:00Z"
}
```

### Question Management
#### List Questions
**Endpoint:** `GET /questions/`  
**Required Role:** `moderator`, `admin`, `superadmin`  

**Query Parameters:**
- `page` (integer): Page number
- `difficulty` (string): Filter by difficulty (`easy`, `medium`, `hard`)
- `search` (string): Search question text
- `created_by` (integer): Filter by creator ID

**Response:** `200 OK`
```json
{
  "count": 100,
  "results": [
    {
      "id": 1,
      "text": "What is 5 × 5?",
      "difficulty": "easy",
      "date_created": "2024-01-10T09:00:00Z",
      "created_by": {
        "name": "Admin User"
      }
    }
  ]
}
```

#### Question Details
**Get Question**  
**Endpoint:** `GET /questions/{question_id}/`  
**Required Role:** `moderator`, `admin`, `superadmin`  
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
      "id": 4,
      "username": "adminjoe",
      "first_name": "Joe",
      "last_name": "Admin"
    }
  }
}
```

### Dashboard
#### Candidate Dashboard
**Endpoint:** `GET /dashboard/candidate/`  
**Required Role:** Any candidate  
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
    "profile_photo": "https://verboheit.s3.eu-north-1.amazonaws.com/candidate_profile_photos/8.jpg"
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
      "open_duration_hours": "12",
      "exam_date": "2024-01-25T14:00:00Z",
      "countdown_minutes": 90,
      "question_count": 25,
      "stage": "screening"
    }
  ]
}
```

#### Staff Dashboard
**Endpoint:** `GET /dashboard/staff/`  
**Required Role:** `moderator`, `admin`, `superadmin`  
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
    "profile_photo": "https://verboheit.s3.eu-north-1.amazonaws.com/staff_profile_photos/7.jpg"
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

### Leaderboard
#### Toggle Leaderboard Visibility
**Endpoint:** `POST /toggle-leaderboard/`  
**Required Role:** `admin`, `superadmin`  
**Request Body:**
```json
{
  "visible": true
}
```

**Response:** `200 OK`
```json
{
  "message": "leaderboard_visible: True"
}
```

#### Publish Leaderboard
**Endpoint:** `POST /publish-leaderboard/`  
**Required Role:** `admin`, `superadmin`  
**Response:** `200 OK`
```json
{
  "message": "Leaderboard published successfully!",
  "published_at": "2024-01-20T18:00:00Z"
}
```

#### Load Leaderboard
**Endpoint:** `GET /load-leaderboard/`  
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

### User Verification

User verification is handled with a focus on security and privacy. Sensitive documents like ID cards are stored in a private storage and can only be accessed via secure, authenticated endpoints that serve the file directly, preventing URL leakage.

---

#### 1. Get Verification Status

Retrieve the verification status of the currently authenticated user.

**Endpoint:** `GET /user/verification/status/`

**Required Role:** Any authenticated user

**Response:** `200 OK`

This response indicates whether documents have been uploaded and the current status of the verification process. It does not contain any sensitive file URLs.

```json
{
    "is_pending": true,
    "is_verified": false,
    "date_created": "2025-08-30T16:33:19Z",
    "date_updated": "2025-08-30T17:59:17Z",
    "documents_uploaded": {
        "profile_photo": true,
        "id_card": true,
        "verification_document": false
    }
}
```

---

#### 2. Submit or Update Verification Documents

This endpoint allows users to submit their documents for the first time (`POST`) or update an existing, unapproved submission (`PATCH`).

**Endpoint:** `POST /user/verification/upload/`, `PATCH /user/verification/upload/`  
**Required Role:** Any authenticated user  
**Headers:**
```text
Authorization: Bearer <access_token>
Content-Type: multipart/form-data
```

**Form Data:**
- `profile_photo` (file): Your profile picture.
- `id_card` (file): A valid identification document.
- `verification_document` Recent school result forcandidates | NIN/Driver's License/Passport for staff

---

##### **A) Initial Submission (`POST`)**
Use this method to submit your verification documents for the first time. Your status will be set to `pending`.

**Conditions:**
- Fails if you are already verified.
- Fails if you already have a verification request pending; in that case, use `PATCH` method to re-upload duing pending verfication.

**Success Response (`200 OK`):**
```json
{
    "detail": "Documents uploaded successfully."
}
```

**Error Response (`400 Bad Request`):**
```json
{
    "detail": "This user has already been verified."
}
```
*or*
```json
{
    "detail": "User already has a verification request pending."
}
```

---

##### **B) Updating a Submission (`PATCH`)**
Use this method to update one or more documents if your initial submission has not yet been approved.

**Conditions:**
- Fails if you are already verified.

**Success Response (`200 OK`):**
The response includes the updated status and a list of which documents have been uploaded.
```json
{
    "detail": "Verification data updated successfully.",
    "verification_data": {
        "is_pending": true,
        "is_verified": false,
        "date_created": "2025-08-30T16:33:19Z",
        "date_updated": "2025-08-31T10:20:00Z",
        "documents_uploaded": {
            "profile_photo": true,
            "id_card": true,
            "verification_document": true
        }
    }
}
```

**Error Response (`400 Bad Request`):**
```json
{
    "detail": "Cannot update verification data for an already verified user."
}
```

---

#### 3. Access Verification Documents

Access uploaded documents. The API serves the file content directly to ensure security.

**For Own Documents:**

**Endpoint:** `GET /user/verification/documents/{file_type}/`

**Required Role:** Any authenticated user

**URL Parameters:**
- `file_type` (string): The type of file to retrieve. Must be one of `id_card`, `verification_document`, or `profile_photo`.

**For Other Users' Documents (SuperAdmin Only):**

**Endpoint:** `GET /user/verification/documents/{file_type}/{user_id}/`

**Required Role:** `superadmin`

**URL Parameters:**
- `file_type` (string): The type of file to retrieve.
- `user_id` (uuid): The ID of the user whose document is being accessed.

**Successful Response:**
- The API will return the raw file content (e.g., an image or a PDF) with the appropriate `Content-Type` header. There is no JSON response body for a successful file retrieval.

**Error Responses:**
- `404 Not Found`: If the file does not exist or has not been uploaded.
- `403 Forbidden`: If you do not have permission to access the document.

---

#### 4. List All Verification Requests (Admin)

Retrieve a list of all user verification submissions for administrative review.

**Endpoint:** `GET /user/verification/list/`

**Required Role:** `admin`, `superadmin`

**Response:** `200 OK`

Returns a list of all verification records, indicating which documents have been provided for each user.

```json
[
    {
        "user_id": "4ecxxxxx-8f43-xxxx-xxxx-xxxxxxxxxx",
        "user_name": "John Doe",
        "email": "john@example.com",
        "is_pending": true,
        "is_verified": false,
        "has_profile_photo": true,
        "has_id_card": true,
        "has_verification_document": false,
        "date_created": "2025-08-30T16:33:19Z"
    },
    {
        "user_id": "a9xxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxx",
        "user_name": "Jane Smith",
        "email": "jane@example.com",
        "is_pending": false,
        "is_verified": true,
        "has_profile_photo": true,
        "has_id_card": true,
        "has_verification_document": true,
        "date_created": "2025-08-29T11:00:00Z"
    }
]
```

---

## Query Parameters
### Common Parameters
| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `page` | integer | Page number for pagination | `?page=2` |
| `limit` | integer | Items per page (max: 100) | `?limit=25` |
| `search` | string | Search across relevant fields | `?search=john` |
| `ordering` | string | Sort results (`field` or `-field`) | `?ordering=-date_created` |

### Filtering Parameters
| Endpoint | Parameter | Type | Description |
|----------|-----------|------|-------------|
| `/candidates/` | `role` | string | Filter by candidate role |
| `/candidates/` | `school` | string | Filter by school name |
| `/candidates/` | `verified` | boolean | Filter by verification status |
| `/staff/` | `role` | string | Filter by staff role |
| `/staff/` | `occupation` | string | Filter by occupation |
| `/exams/` | `stage` | string | Filter by exam stage |
| `/exams/` | `active` | boolean | Filter by active status |
| `/questions/` | `difficulty` | string | Filter by question difficulty |

### Date Filtering
Use ISO 8601 format for date parameters:

| Parameter | Format | Example |
|-----------|--------|---------|
| `date_from` | YYYY-MM-DD | `?date_from=2024-01-01` |
| `date_to` | YYYY-MM-DD | `?date_to=2024-12-31` |
| `created_after` | YYYY-MM-DDTHH:MM:SS | `?created_after=2024-01-01T10:00:00` |

---

## Error Handling
### HTTP Status Codes
| Code | Status | Description |
|------|--------|-------------|
| 200 | OK | Request successful |
| 201 | Created | Resource created successfully |
| 204 | No Content | Resource deleted successfully |
| 400 | Bad Request | Invalid request data or parameters |
| 401 | Unauthorized | Authentication required or invalid token |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource not found |
| 422 | Unprocessable Entity | Validation errors |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server error |

### Error Response Format
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request contains invalid data",
    "details": {
      "field": "username",
      "reason": "Username already exists"
    }
  },
  "timestamp": "2024-01-20T15:30:00Z",
  "request_id": "req_123456789"
}
```

<!-- ### Common Error Codes
| Code | Description |
|------|-------------|
| `AUTHENTICATION_REQUIRED` | Valid authentication token required |
| `INVALID_TOKEN` | Token is expired or invalid |
| `INSUFFICIENT_PERMISSIONS` | User lacks required permissions |
| `VALIDATION_ERROR` | Request validation failed |
| `RESOURCE_NOT_FOUND` | Requested resource doesn't exist |
| `DUPLICATE_RESOURCE` | Resource already exists |
| `RATE_LIMIT_EXCEEDED` | Too many requests |
| `REGISTRATION_CLOSED` | Registration is currently disabled |
| `EXAM_NOT_AVAILABLE` | Exam is not available for this user |
| `EXAM_ALREADY_TAKEN` | Candidate has already taken this exam | -->

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
```text
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1640995200
```

### Rate Limit Exceeded
**Response:** `429 Too Many Requests`
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded. Please try again later.",
    "details": {
      "limit": 1000,
      "remaining": 0,
      "reset_time": "2024-01-21T00:00:00Z"
    }
  }
}
```

---

## Versioning
### Current Version
The API is currently at version `v1`. All endpoints are prefixed with `/api/v1/`.

### Versioning Strategy
- **Backwards Compatibility**: Minor changes maintain backwards compatibility
- **Breaking Changes**: Major version increments for breaking changes
- **Deprecation**: 6-month notice period for deprecated endpoints
- **Version Support**: Latest 2 major versions supported

---

## Interactive Documentation
Explore the API interactively using our documentation interfaces:
- **Swagger UI**: `https://vmlc-api.onrender.com/docs/swagger/`
- **ReDoc**: `https://vmlc-api.onrender.com/docs/redoc/`

---

## Support
For technical support, API key requests, or questions:
- **Email:** `olujay.dev@gmail.com`
- **Discord:** `@olujay`
- **X:** `@theolujay`
- **Response Time:** Within 48 hours for support requests
- **API Key Requests:** Include organization name and intended use case

---

## Changelog
### Version 0.1.0 (Current)
- Initial API release
- Complete user management system
- Exam administration features
- Leaderboard functionality
- Role-based access control

_Last Updated: July 2025_