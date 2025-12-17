# Rate Limiting

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
