# Exam Direct Access System

The Exam Direct Access system allows eligible candidates to access their exams directly via a unique, single-use passcode embedded in a URL. This improves accessibility by reducing the friction of the standard login process while maintaining security.

## How it Works

1.  **Generation**: When an exam is scheduled (transitions from `DRAFT` to `SCHEDULED`), a unique passcode is generated for every eligible candidate and stored in the `ExamAccessPasscode` model.
2.  **Notification**: An email is sent to each candidate containing a unique URL.
    *   URL Format: `https://portal.verboheit.org/?passcode=<UNIQUE_PASSCODE>`
3.  **Authentication**:
    *   The frontend extracts the `passcode` from the query parameter.
    *   The frontend sends a POST request to the Direct Access Login endpoint.
    *   **Validity Check**: The system verifies that:
        *   The passcode exists and has not been marked as `USED`.
        *   The current time is between the exam's `scheduled_date` and its `concluded_at` (expiry) time.
    *   If valid, the API returns a set of JWT tokens (access and refresh) and basic user info.
    *   The passcode status is then updated to `USED`.
4.  **Identity Verification**: Before the candidate can begin the exam (even after authentication), they must submit a face capture image for identity verification.
5.  **Exam Start**: Once identity verification is successful (status becomes `PENDING`), the candidate can proceed to "take" the exam, which transitions the access status to `STARTED`.

## API Specification

### Direct Access Login

**Endpoint**: `POST /api/v2/auth/direct-access/`

**Headers**:
*   `x-api-key`: Required

**Request Body**:
```json
{
  "passcode": "string (The unique passcode from the URL)"
}
```

**Successful Response (200 OK)**:
```json
{
  "refresh": "JWT refresh token",
  "access": "JWT access token",
  "profile": {
    "id": "UUID",
    "user": { ... },
    "is_setup_complete": true
  }
}
```

**Error Responses**:
*   `400 Bad Request`: Passcode missing.
*   `403 Forbidden`: Invalid passcode, used passcode, expired passcode, or exam is not currently in `SCHEDULED` or `ONGOING` status.

### Exam Face Capture

**Endpoint**: `POST /api/v2/exams/<uuid:exam_id>/face-capture/`

**Headers**:
*   `Authorization`: Bearer `<JWT_ACCESS_TOKEN>`
*   `Content-Type`: `multipart/form-data`

**Request Body**:
*   `face_capture`: Image file (JPG/PNG, max 5MB)

**Successful Response (200 OK)**:
```json
{
  "message": "Face capture uploaded successfully."
}
```

**Error Responses**:
*   `401 Unauthorized`: Missing or invalid token.
*   `403 Forbidden`: User is not a candidate.
*   `404 Not Found`: Exam not found.

## Frontend Integration Instructions

1.  **URL Handling**: Upon application load, check for the presence of a `passcode` query parameter in the URL.
2.  **Authentication Trigger**: If a `passcode` exists:
    *   Show a loading state (e.g., "Authenticating your direct access...").
    *   Call the `POST /api/v2/auth/direct-access/` endpoint.
3.  **Login Success**:
    *   Store the returned JWT tokens as you would with a normal login.
    *   Check the candidate's dashboard or exam status.
4.  **Identity Verification Step**: Before calling the `take-exam` endpoint:
    *   Prompt the candidate to capture their face using their camera.
    *   Upload the image to `POST /api/v2/exams/<uuid:exam_id>/face-capture/`.
5.  **Taking the Exam**:
    *   After a successful face capture upload, call `GET /api/v2/exams/<uuid:exam_id>/take-exam/` to receive the questions and start the exam timer.
    *   *Note*: Attempting to call `take-exam` without a prior face capture will result in a `403 Forbidden` error with the message: "Identity verification (face capture) required before taking the exam."
6.  **Login Failure**:
    *   If authentication fails, display an appropriate error message.
    *   Provide an option to log in normally using email and password.
7.  **Status Check**: Remember that direct access is only valid while the exam status is `ONGOING`. If a candidate clicks the link too early (when it's still `SCHEDULED`), they will be informed that the access is not yet valid.

## Admin Management

Staff with Admin access can manually trigger the generation and sending of passcodes for one or more exams via the Django Admin interface:
1.  Go to **VMLC > Exams**.
2.  Select the desired exams.
3.  Choose the action **"Generate and Send Direct Access Passcodes"** from the dropdown.
4.  Click **Go**.
