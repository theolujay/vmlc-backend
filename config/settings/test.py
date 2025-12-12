"""
Test environment for CI/CD pipelines.
"""

import os
import dj_database_url

from .base import *

SECRET_KEY = "this-is-a-test-secret-key--do-not-use-in-production"

DEBUG = False
TESTING = True
INTERNAL_IPS = ["localhost"]
ALLOWED_HOSTS = ["localhost"]
ADMIN_URL = "admin/"
CONTACT_EMAIL = "admin@localhost"
CONTACT_URL = "http://localhost/contact"
BASE_URL = "http://localhost"
DATABASE_URL = "postgresql://testuser:testpassword@db:5432/testdb"
DATABASES = {
    "default": dj_database_url.config(
        default=DATABASE_URL,
    )
}
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "servestatic.storage.CompressedManifestStaticFilesStorage",
    },
}



# ============================================================================
# CELERY CONFIGURATION - Docker Development Environment
# ============================================================================

# Docker service names for Redis broker
CELERY_BROKER_URL = "redis://redis:6379/0"
CELERY_RESULT_BACKEND = "redis://redis:6379/0"


CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

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

AWS_S3_LOCATION_PREFIX = os.getenv("AWS_S3_LOCATION_PREFIX", "test")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME")
AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME")
AWS_S3_CUSTOM_DOMAIN = (
    f"{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com"
)

AWS_S3_CUSTOM_DOMAIN = "localhost:8000"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        # "verbose": {
        #     "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
        #     "style": "{",
        # },
        # "simple": {
        #     "format": "{levelname} {name} {message}",
        #     "style": "{",
        # },
        "colored": {
            "()": "colorlog.ColoredFormatter",
            "format": "%(log_color)s%(levelname)-8s%(reset)s %(blue)s%(name)s%(reset)s %(message)s",
        },
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(name)s %(levelname)s %(module)s %(lineno)d %(message)s",
        },
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            # "formatter": "colored" if os.getenv("USE_COLORED_LOGS", "true").lower() == "true" else "simple",
            "formatter": "colored",
        },
        #     "file": {
        #         "level": "DEBUG",
        #         "class": "logging.handlers.RotatingFileHandler",
        #         "filename": str(LOG_DIR / "vmlc_docker_dev.log"),
        #         "formatter": "json",
        #         "maxBytes": 5 * 1024 * 1024,  # 5MB
        #         "backupCount": 3,
        #         "encoding": "utf-8",
        #         "delay": True,
        #     },
    },
    "root": {
        "level": "WARNING",
        "handlers": ["console"],
    },
    "loggers": {
        # Your app - keep detailed logging
        "vmlc": {
            "level": "DEBUG",
            "handlers": ["console"],
            "propagate": False,
        },
        "comms": {
            "level": "DEBUG",
            "handlers": ["console"],
            "propagate": False,
        },
        # Django - only important stuff
        "django": {
            "level": "WARNING",  # Only warnings/errors
            "handlers": ["console"],
            "propagate": False,
        },
        # Celery - moderate logging
        "celery": {
            "level": "INFO",  # Changed from DEBUG
            "handlers": ["console"],
            "propagate": False,
        },
        # Third-party noise reduction
        "urllib3": {"level": "ERROR"},  # Only errors
        "requests": {"level": "ERROR"},  # Only errors
        "boto3": {"level": "ERROR"},  # Only errors
        "botocore": {"level": "ERROR"},  # Only errors
        "django.db.backends": {"level": "ERROR"},  # No query spam
        # Additional noise reducers
        "django.request": {"level": "ERROR"},  # Only 4xx/5xx requests
        "django.security": {"level": "WARNING"},  # Security warnings only
        # "asyncio": {"level": "WARNING"},        # Async noise reduction
    },
}


FRONTEND_BASE_URL = "https://test-portal.verboheit.org"
FRONTEND_LOGIN = FRONTEND_BASE_URL + "/login/"
FRONTEND_REGISTER_CANDIDATE = FRONTEND_BASE_URL + "/register/"
FRONTEND_REGISTER_STAFF = FRONTEND_BASE_URL + "/register/staff/"
SUPPORT_EMAIL = "verboheitmlc@gmail.com"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    }
}
