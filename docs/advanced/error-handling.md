# Error Handling


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
