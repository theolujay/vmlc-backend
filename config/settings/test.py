"""
Test environment settings for CI/CD pipelines and local testing.
"""

import dj_database_url
from .base import *

# ============================================================================
# TEST-SPECIFIC SETTINGS
# ============================================================================
SECRET_KEY = "this-is-a-test-secret-key--do-not-use-in-production"
DEBUG = True
TESTING = True

# Add daphne for testing ASGI applications
INSTALLED_APPS.insert(0, "daphne")

# Configure test database
DATABASES = {
    "default": dj_database_url.config(
        default="postgresql://testuser:testpassword@db:5432/testdb"
    )
}

# Use FileSystemStorage for tests to avoid dependency on S3
USE_S3 = False
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "servestatic.storage.CompressedManifestStaticFilesStorage"
    },
}

# Celery configuration for synchronous task execution in tests
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Cache configuration for tests (use a separate Redis DB or dummy cache)
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://redis:6379/1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "COMPRESSOR": "django_redis.compressors.zlib.ZlibCompressor",
            "SERIALIZER": "django_redis.serializers.json.JSONSerializer",
        },
        "KEY_PREFIX": "vmlc_test_sync",
        "TIMEOUT": 300,
    },
}
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "WARNING"},
    "loggers": {
        "django.db.backends": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        }
    },
}

# Override sensitive/service-related settings for tests
TWILIO_ACCOUNT_SID = "test_twilio_sid"
TWILIO_AUTH_TOKEN = "test_twilio_token"
TWILIO_FROM_PHONE = "+15005550006"
SLACK_WEBHOOK_URL = None
BROADCAST_WEBHOOK_URL = None
