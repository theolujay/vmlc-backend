# Base URLs

The VMLC API is available at different endpoints depending on your environment.

## Production

```
https://api.verboheit.org/v1/
```

Use this for production applications. This environment is stable and monitored 24/7.

## Staging

```
https://staging-api.verboheit.org/v1/
```

Use this for testing and development. This environment may have experimental features.

## Environment-Specific Considerations

### Production

- ✅ High availability
- ✅ Regular backups
- ✅ Monitoring and alerts
- ✅ Rate limiting enforced

### Staging

- 🧪 Testing environment
- 🧪 May have downtime
- 🧪 Data may be reset periodically
- 🧪 Relaxed rate limits

## Best Practices

1. **Use environment variables** for base URLs
2. **Never hardcode URLs** in your application
3. **Test in staging** before deploying to production
4. **Monitor your API usage** in production

## Example Configuration

=== "Python"
```python
import os

    BASE_URL = os.getenv(
        'VMLC_API_BASE_URL',
        'https://api.verboheit.org/v1/'
    )
    ```

=== "JavaScript"
`javascript
    const BASE_URL = process.env.VMLC_API_BASE_URL || 
                     'https://api.verboheit.org/v1/';
    `
