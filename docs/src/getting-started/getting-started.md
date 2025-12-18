# Getting Started

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
