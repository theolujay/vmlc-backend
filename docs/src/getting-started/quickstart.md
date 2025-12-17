# Quick Start Guide

Get up and running with the VMLC API in minutes.

## Step 1: Get Your API Key

Contact us at theolujay@gmail.com to request an API key.

## Step 2: Make Your First Request

=== "Python"
```python
import requests

    # Check API health
    response = requests.get(
        "https://api.verboheit.org/v1/health/",
        headers={"X-Api-Key": "your_api_key"}
    )

    print(response.json())
    # Output: {"status": "healthy", "timestamp": "2025-12-16T..."}
    ```

=== "JavaScript"
```javascript
const response = await fetch(
'https://api.verboheit.org/v1/health/',
{
headers: {
'X-Api-Key': 'your_api_key'
}
}
);

    const data = await response.json();
    console.log(data);
    ```

## Step 3: Authenticate a User

```python
import requests

url = "https://api.verboheit.org/v1/auth/login/"
headers = {
    "X-Api-Key": "your_api_key",
    "Content-Type": "application/json"
}
payload = {
    "email": "user@example.com",
    "password": "password123"
}

response = requests.post(url, json=payload, headers=headers)
tokens = response.json()

access_token = tokens["access"]
refresh_token = tokens["refresh"]
```

## Step 4: Make Authenticated Requests

```python
headers = {
    "X-Api-Key": "your_api_key",
    "Authorization": f"Bearer {access_token}"
}

response = requests.get(
    "https://api.verboheit.org/v1/candidates/me/",
    headers=headers
)

profile = response.json()
print(profile)
```

## Next Steps

- Explore the [full API reference](../api/index.md)
- Learn about [user roles and permissions](../roles/index.md)
- Check out [advanced topics](../advanced/index.md)
