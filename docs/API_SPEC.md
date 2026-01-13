# Verboheit Mathematics League Competition - API Specification

This documentation outlines the backend API integration for the VMLC landing page.

---

## 1. General Configuration

### Base URL
The API base URL is configured via environment variables.
- **Base URL:** Defined by `VITE_PORTAL_URL` (e.g., `https://api.verboheit.org`).
- **Sanitization:** The frontend strips trailing slashes from this URL before appending endpoints.

### Authentication
Requests require an API key passed in the `x-api-key` header.

| Endpoint | Environment Variable | Header Key |
| :--- | :--- | :--- |
| `/register/` | `VITE_API_KEY` | `x-api-key` |
| `/support-us/` | `VITE_API_KEY` | `x-api-key` |
| `/pre-register/` | `VITE_API_KEY` | `x-api-key` |

---

## 2. Registration Status

Check if registration is currently open for candidates and staff, and see scheduled closing dates.

- **Endpoint:** `/v2/registration/`
- **Method:** `GET`
- **Content-Type:** `application/json`
- **Authentication:** None (Public)

### Success Response (200 OK)
```json
{
  "candidate_registration": {
    "is_open": true,
    "closing_date": "2026-01-20T23:59:59Z"
  },
  "staff_registration": {
    "is_open": true,
    "closing_date": null
  },
  "support_email": "support@verboheit.org"
}
```

| Key | Type | Description |
| :--- | :--- | :--- |
| `candidate_registration` | `object` | Status for candidate registration. |
| `staff_registration` | `object` | Status for volunteer/staff registration. |
| `support_email` | `string` | System support email address. |

#### Detailed Status Object
| Key | Type | Description |
| :--- | :--- | :--- |
| `is_open` | `boolean` | `true` if registration is active. |
| `closing_date` | `string | null` | ISO 8601 timestamp of scheduled auto-close, or `null` if not set. |

---

## 3. User Registration

Registers a new user as either a **Candidate** or a **Volunteer**.

- **Endpoint:** `/v2/register/`
- **Method:** `POST`
- **Content-Type:** `multipart/form-data`

### Request Parameters (Form Data)

#### Common Fields
| Key | Type | Description |
| :--- | :--- | :--- |
| `user_type` | `string` | `candidate` or `volunteer`. |
| `first_name` | `string` | User's first name. |
| `last_name` | `string` | User's last name. |
| `email` | `string` | Valid email address. |
| `phone_number`| `string` | Phone number (e.g., `+234...`). |
| `state` | `string` | State of residence (e.g., Lagos, Ogun, etc). |
| `document` | `file` | ID or Result upload (Max 5MB). |
| `document_type`| `string` | `NIN` or `school result` (Candidate) / `NIN`, `passport`, or `drivers license` (Volunteer). |
| `consent` | `string` | `"true"` (Boolean sent as string in FormData). Must be true to proceed. |

#### Candidate-Specific Fields (Required if `user_type` is `candidate`)
| Key | Type | Description |
| :--- | :--- | :--- |
| `school_name` | `string` | Full name of the secondary school. |
| `school_type` | `string` | `public` or `private`. |
| `current_class`| `string` | `SS1`, `SS2`, or `SS3`. |

#### Volunteer-Specific Fields (Required if `user_type` is `volunteer`)
| Key | Type | Description |
| :--- | :--- | :--- |
| `occupation` | `string` | Current profession or status. |

---

## 4. Support Inquiry

For sponsorships, partnerships, and other forms of support.

- **Endpoint:** `/v2/support-us/`
- **Method:** `POST`
- **Content-Type:** `application/json`

### Request Body (JSON)
| Key | Type | Description |
| :--- | :--- | :--- |
| `full_name` | `string` | User's full name. |
| `email` | `string` | Valid email address. |
| `organization`| `string` | (Optional) Organization name. |
| `support_type` | `string` | `financial`, `partnership`, `media`, `mentorship`, or `other`. |
| `phone_number`| `string` | (Optional) Contact phone. |
| `message` | `string` | Detailed inquiry message. |
| `consent` | `boolean` | `true` or `false`. |

---

## 5. Pre-Registration

Lead collection for interested participants.

- **Endpoint:** `/v2/pre-register/`
- **Method:** `POST`
- **Content-Type:** `application/json`

### Request Body (JSON)
| Key | Type | Description |
| :--- | :--- | :--- |
| `full_name` | `string` | User's full name. |
| `email` | `string` | Valid email address. |
| `phone_number` | `string` | Contact phone. |
| `interest_type` | `string` | `candidate` or `volunteer`. |

---

## 6. Response Formats

The API returns JSON responses.

### Success (201 Created)
Returned when a registration or pre-registration is successfully created.
```json
{
  "status": "success",
  "message": "Action completed successfully."
}
```

### Error Responses

#### Validation Error (400 Bad Request)
Returned when input data fails validation (e.g., invalid email, missing fields).
```json
{
  "status": "error",
  "message": "Validation failed.",
  "errors": {
    "email": [
      "A user with this email already exists."
    ],
    "phone_number": [
      "Enter a valid Nigerian phone number."
    ],
    "non_field_errors": [
      "Global error message if applicable."
    ]
  }
}
```

#### Permission / General Error (403 Forbidden / 400 Bad Request)
Returned when an action is not allowed (e.g., registration closed, already authenticated) or for other generic errors.
```json
{
  "detail": "Registration is currently closed."
}
```

---

## 7. Implementation Notes

- **Multipart Data:** The browser handles the boundary for `multipart/form-data`. Do not manually set `Content-Type` headers for `/v2/register/`.
- **File Validation:** The frontend filters files by extension (.pdf, .jpg, .png) and enforces a 5MB size limit.
- **CORS:** Ensure the backend allows requests from the landing page domain and allows the `x-api-key` header.