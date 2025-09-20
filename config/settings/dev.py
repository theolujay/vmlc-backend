"""
Local development environment settings.
This settings configuration is used when running without Docker containers locally.
Uses SQLite
"""

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")

from .base import *

DEBUG = True

INTERNAL_IPS = [
    ip.strip() for ip in os.getenv("INTERNAL_IPS", "").split(",") if ip.strip()
]

ALLOWED_HOSTS = [
    host.strip() for host in os.getenv("ALLOWED_HOSTS", "").split(",") if host.strip()
]
INSTALLED_APPS += [
    "debug_toolbar",
    "django_extensions",
    # "silk",  # SQL profiling
]
MIDDLEWARE += [
    "debug_toolbar.middleware.DebugToolbarMiddleware",
    # "silk.middleware.SilkyMiddleware",
]

ADMIN_URL = os.getenv("DJANGO_ADMIN_URL", "admin/")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

SIMPLE_JWT.update(
    {
        "ACCESS_TOKEN_LIFETIME": timedelta(days=3),
        "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
        "ROTATE_REFRESH_TOKENS": True,
    }
)

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",  # Frontend
    "http://127.0.0.1:3000",
    "http://localhost:8000",  # Backend
    "http://127.0.0.1:8000",
    "https://aece03f54dba.ngrok-free.app",
]

CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = True  # ← Enable TLS for Gmail port 587
EMAIL_USE_SSL = False  # ← Keep SSL disabled when using TLS
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "dev@vmlc.local")

# Fallback to console if no EMAIL_HOST is provided
if not os.getenv("EMAIL_HOST"):
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"


BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
TOS_URL = os.getenv("TOS_URL", f"{BASE_URL}/terms/")
CONTACT_EMAIL = os.getenv("CONTACT_EMAIL", "dev@vmlc.local")
CONTACT_URL = os.getenv("CONTACT_URL", f"{BASE_URL}/contact/")
LICENSE_URL = os.getenv("LICENSE_URL", f"{BASE_URL}/license/")
LOGO_URL = os.getenv("LOGO_URL", f"{BASE_URL}/static/images/logo.png")


# Local Redis for development
CELERY_BROKER_URL = "redis://localhost:6379/0"
CELERY_RESULT_BACKEND = "redis://localhost:6379/0"

# Development-specific overrides
CELERY_WORKER_LOG_COLOR = True  # Enable colored logs in dev
CELERY_TASK_ALWAYS_EAGER = False  # Use real async processing
CELERY_TASK_EAGER_PROPAGATES = True

# Lower concurrency for development
CELERY_WORKER_CONCURRENCY = 2

# ============================================================================
# CACHE CONFIGURATION - Development Environment
# ============================================================================

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://localhost:6379/1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "CONNECTION_POOL_KWARGS": {
                "retry_on_timeout": True,
                "health_check_interval": 30,
            },
        },
        "KEY_PREFIX": "vmlc_dev_sync",
        "TIMEOUT": 300,
    },
    "async": {
        "BACKEND": "django_async_redis.cache.RedisCache",
        "LOCATION": "redis://localhost:6379/2",
        "OPTIONS": {
            "CLIENT_CLASS": "django_async_redis.client.DefaultClient",
        },
        "KEY_PREFIX": "vmlc_dev_async",
        "TIMEOUT": 300,
    },
}  # remember to run `sudo systemctl start redis-server` or use  bash alias="pyma runserver w-redis"

USE_S3 = os.getenv("USE_S3", "false").lower() == "true"

if USE_S3:

    def validate_aws_config():
        """Validate that all required AWS environment variables are set."""
        required_vars = [
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_STORAGE_BUCKET_NAME",
            "AWS_S3_REGION_NAME",
        ]

        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise ImproperlyConfigured(
                f"Missing required AWS environment variables: {', '.join(missing_vars)}"
            )

    validate_aws_config()

    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
    AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME")
    AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME")

    AWS_S3_CUSTOM_DOMAIN = (
        f"{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com"
    )
    AWS_S3_OBJECT_PARAMETERS = {
        "CacheControl": "max-age=86400",
        "ServerSideEncryption": "AES256",
        "ACL": "bucket-owner-full-control",
    }
    AWS_S3_VERIFY = True
    AWS_S3_FILE_OVERWRITE = False  # Prevent accidental overwrites
    AWS_QUERYSTRING_AUTH = True  # Use signed URLs for private files
    AWS_QUERYSTRING_EXPIRE = 3600  # 1 hour expiry for signed URLs
    AWS_S3_SIGNATURE_VERSION = "s3v4"  # Use latest signature version
    AWS_PRELOAD_METADATA = True  # Better performance
    AWS_S3_MAX_MEMORY_SIZE = 100 * 1024 * 1024  # 100MB max memory usage

    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
            "OPTIONS": {
                "bucket_name": AWS_STORAGE_BUCKET_NAME,
                "region_name": AWS_S3_REGION_NAME,
                "object_parameters": AWS_S3_OBJECT_PARAMETERS,
                "file_overwrite": AWS_S3_FILE_OVERWRITE,
                "querystring_auth": AWS_QUERYSTRING_AUTH,
                "querystring_expire": AWS_QUERYSTRING_EXPIRE,
                "signature_version": AWS_S3_SIGNATURE_VERSION,
                "location": "media",
            },
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }
else:
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "vmlc": {
            "level": "DEBUG",
            "handlers": ["console"],
            "propagate": True,
        },
    },
}

DATA_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024  # 2MB (default is 2.5MB)
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024  # 2MB (default is 2.5MB)

DEBUG_TOOLBAR_CONFIG = {
    "SHOW_TEMPLATE_CONTEXT": True,
    "SHOW_TOOLBAR_CALLBACK": lambda request: DEBUG,  # Always show in debug mode
    "INTERCEPT_REDIRECTS": False,
}


GRAPH_MODELS = {
    "all_applications": True,
    "group_models": True,
}


# # Silk profiling configuration (SQL query profiler)
# SILKY_PYTHON_PROFILER = True
# SILKY_PYTHON_PROFILER_BINARY = True
# SILKY_AUTHENTICATION = True  # Require authentication
# SILKY_AUTHORISATION = True   # Require authorization

# Development security settings (less restrictive)
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_BROWSER_XSS_FILTER = False
SECURE_CONTENT_TYPE_NOSNIFF = False

# Development session settings
SESSION_COOKIE_AGE = 60 * 60 * 24 * 7  # 1 week
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# # Optional: Database query logging in development
# if os.getenv("LOG_QUERIES", "false").lower() == "true":
#     LOGGING["loggers"]["django.db.backends"] = {
#         "level": "DEBUG",
#         "handlers": ["console"],
#         "propagate": False,
#     }
