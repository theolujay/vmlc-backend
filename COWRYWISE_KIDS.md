# Cowrywise Kids Feature Documentation

The Cowrywise Kids feature allows candidates to link their Cowrywise Kid profiles to their Verboheit MLC accounts.

## API Specification

### Create Cowrywise Kid Profile

Creates a new Cowrywise Kid profile for the authenticated candidate.

- **URL:** `/v1/cowrywise-kids/`
- **Method:** `POST`
- **Authentication:** Required (Candidate only)
- **Permissions:** `CandidatePermissions`

#### Request Body

| Field | Type | Description |
| :--- | :--- | :--- |
| `username` | `string` | **Required.** The Cowrywise Kid username. |

**Example Request:**
```json
{
  "username": "candidate0.vmlc@mailsac.com"
}
```

#### Response

**Success (201 Created):**
| Field | Type | Description |
| :--- | :--- | :--- |
| `username` | `string` | The linked Cowrywise Kid username. |
| `candidate` | `integer` | The ID of the candidate profile. |
| `created_at` | `string` | The timestamp when the profile was created. |
| `updated_at` | `string` | The timestamp when the profile was last updated. |

**Example Response:**
```json
{
  "username": "candidate0.vmlc@mailsac.com",
  "candidate": 42,
  "created_at": "2026-02-25T10:00:00Z",
  "updated_at": "2026-02-25T10:00:00Z"
}
```

#### Error Responses

- **400 Bad Request:**
  - If the username is missing or invalid.
  - If a validation error occurs during creation.
  - *Response body:* `{"error": "Validation error: ..."}`

- **403 Forbidden:**
  - If the candidate is not enrolled in any active competition.
  - *Response body:* `{"error": "You are not enrolled in any competition."}`

- **401 Unauthorized:**
  - If the user is not authenticated.

## Implementation Details

- **View:** `CowrywiseKidProfileView` in `identity/views.py`
- **Serializer:** `CowrywiseKidProfileSerializer` in `identity/serializers/cowrywise_kid.py`
- **Model:** `CowrywiseKidProfile` in `identity/models.py`
- **Events:** Logs `COWRYWISE_KID_REGISTRATION` upon successful creation.

## Profile Data

Upon successful login or when fetching a user's profile, a `has_cowrywise_kid_profile` boolean flag is included in the candidate's profile data. This flag can be used to determine if a candidate has already linked their Cowrywise Kid profile.
