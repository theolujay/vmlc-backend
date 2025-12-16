# Authentication

The VMLC API uses a dual authentication system combining API keys and JWT tokens.

## API Key Authentication

All requests require an `X-Api-Key` header:

```http
X-Api-Key: your_api_key_here
```

## JWT Token Authentication

For user-specific operations, include a JWT access token:

```http
Authorization: Bearer your_access_token
```

## Getting Tokens

See the [Authentication API Reference](../api.md#authentication) for details on obtaining access tokens.

## Example Request

=== "Python"
    ```python
    import requests
    
    headers = {
        "X-Api-Key": "your_api_key",
        "Authorization": "Bearer your_access_token"
    }
    
    response = requests.get(
        "https://api.verboheit.org/v1/candidates/me/",
        headers=headers
    )
    ```

=== "cURL"
    ```bash
    curl -X GET "https://api.verboheit.org/v1/candidates/me/" \
      -H "X-Api-Key: your_api_key" \
      -H "Authorization: Bearer your_access_token"
    ```
