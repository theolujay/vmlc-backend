# Submit Answers API (V2)

Handles the submission of a candidate's answers for a specific exam. This endpoint is designed to be highly resilient to concurrent requests and late submissions.

## Endpoint
`POST /vmlc/v2/exams/<exam_id>/submit/`

## Authentication
- **Permissions**: `CandidatePermissions` (User must be an authenticated candidate).
- **Scope**: The candidate must have an active `ExamAccess` record for the given `exam_id`.

## Request Body
```json
{
  "is_auto_submit": boolean,
  "answers": [
    {
      "question": "integer (ID)",
      "selected_option": "string (A, B, C, D, or empty)"
    }
  ]
}
```

### Fields

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `is_auto_submit` | boolean | Yes | Indicates how the submission was triggered. `true` = system auto-submitted when the candidate's countdown timer expired. `false` = candidate manually submitted. |
| `answers` | array | Yes | List of the candidate's answers. Must contain at least one answer. |
| `answers[].question` | integer | Yes | The question ID. |
| `answers[].selected_option` | string | No | The selected answer (A, B, C, D, or empty string for unanswered). |

## Core Logic & Lifecycle

### 1. Concurrency Control (Atomic Locking)
To prevent race conditions (e.g., a candidate clicking "Submit" twice rapidly or from two different tabs), the view uses a **database-level transaction lock**:
- It acquires a `select_for_update()` lock on the candidate's `ExamAccess` record.
- Any subsequent requests for the same candidate/exam pair will block until the first one completes.

### 2. Status Validation
Before processing, the system checks the current `status` of the `ExamAccess` record:
- If status is `SUBMITTED`, `EXPIRED`, or `FAILED`, the request is rejected with a `400 Bad Request`.

### 3. Expiration & Grace Period
The system evaluates two conditions to allow a submission:
1. **Global Window**: Is the exam still globally open (`exam.is_currently_open`)?
2. **Personal Window**: Is the candidate within their personal countdown timer? 
   - A **5-minute grace period** (`GRACE_PERIOD_MINUTES`) is added to the candidate's personal `deadline`.
   - If the candidate submits within `deadline + 5 minutes`, the submission is accepted to account for network latency.

### 4. Data Persistence
Once validated:
- A `CandidateExamResult` record is created.
- `CandidateAnswer` records are bulk-created for all submitted answers.
- The `ExamAccess` record is updated:
  - `status` set to `SUBMITTED`
  - `submitted_at` set to current timestamp.

### 5. Post-Submission Actions
- **Cache Invalidation**: The candidate's dashboard and status caches are cleared.
- **Notification**: A success email is queued via Celery to the candidate.

## Responses

### Success (201 Created)
```json
{
  "message": "Answers submitted successfully!"
}
```

### Errors
| Code | Reason |
| :--- | :--- |
| **400** | Duplicate submission or access has already expired. |
| **403** | Exam is closed (past grace period) or candidate does not have access. |
| **404** | Exam ID not found. |
