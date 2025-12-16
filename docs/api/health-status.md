# Health & Status


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

### Registration Status
This endpoint provides a public status check for candidate and staff registrations. It indicates whether new registrations are currently open or closed, which can be controlled by feature flags.

**Endpoint:** `GET /registration/`
**Required Role:** None (Public)

**Response:** `200 OK`
```json
{
  "is_candidate_reg_open": true,
  "is_staff_reg_open": false,
  "support_email": "verboheitmlc@gmail.com"
}
```

---
