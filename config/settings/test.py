"""
Test environment settings for CI/CD pipelines and local testing.
"""

import dj_database_url
from .base import *

# ============================================================================
# TEST-SPECIFIC SETTINGS
# ============================================================================
SECRET_KEY = "dummy"
DEBUG = False
TESTING = True
APP_ENVIRONMENT = "test"
# Add daphne for testing ASGI applications
if "daphne" not in INSTALLED_APPS:
    INSTALLED_APPS.insert(0, "daphne")

# Remove debug_toolbar if it was added by base.py
if "debug_toolbar" in INSTALLED_APPS:
    INSTALLED_APPS.remove("debug_toolbar")

# Remove debug_toolbar middleware if it was added by base.py
MIDDLEWARE = [m for m in MIDDLEWARE if "debug_toolbar" not in m]

# Disable DRF throttling in tests
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_THROTTLE_CLASSES": [],
    "DEFAULT_THROTTLE_RATES": {},
}

# Configure test database
DATABASES = {
    "default": dj_database_url.config(
        default="postgresql://testuser:testpassword@db:5432/testdb"
    )
}

# DATABASE_URL = read_secret("DATABASE_URL", f"sqlite:///{BASE_DIR / 'db.sqlite3'}")
# DATABASES = {"default": dj_database_url.parse(DATABASE_URL.replace("db", "localhost"))}

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
        # "LOCATION": "redis://localhost:6379/1",
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


# Speed up tests and avoid migration issues by building DB from models
class DisableMigrations:
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None


MIGRATION_MODULES = DisableMigrations()

# Override sensitive/service-related settings for tests
TWILIO_ACCOUNT_SID = "test_twilio_sid"
TWILIO_AUTH_TOKEN = "test_twilio_token"
TWILIO_FROM_PHONE = "+15005550006"
SLACK_WEBHOOK_URL = None
BROADCAST_WEBHOOK_URL = None

KUDI_API_KEY = "test_kudi_api_key"
KUDI_SENDER_ID = "TEST"
KUDI_GATEWAY = "direct-delivery"
SMS_PROVIDER = "twilio"  # Default to twilio for existing tests
