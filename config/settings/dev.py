"""
Local development environment settings.
This settings configuration is used when running without Docker containers locally.
Uses SQLite
"""

import sys
import os
from datetime import timedelta
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")


def read_secret(secret_name, default=""):
    """Read secret from file if SECRET_NAME_FILE env var exists"""
    file_path = os.getenv(f"{secret_name}_FILE")
    if file_path and os.path.exists(file_path):
        with open(file_path, "r") as f:
            return f.read().strip()
    return os.getenv(secret_name, default)


SECRET_KEY = read_secret("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("The SECRET_KEY environment variable is not set.")

from .base import *

DEBUG = True

INTERNAL_IPS = [
    ip.strip() for ip in read_secret("INTERNAL_IPS", "").split(",") if ip.strip()
]

ALLOWED_HOSTS = [
    host.strip() for host in read_secret("ALLOWED_HOSTS", "").split(",") if host.strip()
]

if "test" not in sys.argv:
    INSTALLED_APPS += [
        "debug_toolbar",
        "django_extensions",
        "servestatic.runserver_nostatic",
        # "silk",  # SQL profiling
    ]
    MIDDLEWARE += [
        "debug_toolbar.middleware.DebugToolbarMiddleware",
        # "silk.middleware.SilkyMiddleware",
    ]

ADMIN_URL = read_secret("DJANGO_ADMIN_URL", "admin/")

# DATABASES = {
#     "default": {
#         "ENGINE": "django.db.backends.sqlite3",
#         "NAME": BASE_DIR / "db.sqlite3",
#     }
# }


DATABASES = {
    "default": dj_database_url.parse(read_secret("NEON_DB_URL", "sqlite:///db.sqlite3"))
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
EMAIL_HOST = read_secret("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(read_secret("EMAIL_PORT", "587"))
EMAIL_HOST_USER = read_secret("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = read_secret("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = True  # ← Enable TLS for Gmail port 587
EMAIL_USE_SSL = False  # ← Keep SSL disabled when using TLS
DEFAULT_FROM_EMAIL = read_secret("DEFAULT_FROM_EMAIL", "dev@vmlc.local")

# Fallback to console if no EMAIL_HOST is provided
if not read_secret("EMAIL_HOST"):
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"


BASE_URL = read_secret("BASE_URL", "http://localhost:8000")
TOS_URL = read_secret("TOS_URL", f"{BASE_URL}/terms/")
CONTACT_EMAIL = read_secret("CONTACT_EMAIL", "dev@vmlc.local")
CONTACT_URL = read_secret("CONTACT_URL", f"{BASE_URL}/contact/")
LICENSE_URL = read_secret("LICENSE_URL", f"{BASE_URL}/license/")
LOGO_URL = read_secret("LOGO_URL", f"{BASE_URL}/static/images/logo.png")


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

USE_S3 = read_secret("USE_S3", "false").lower() == "true"
AWS_S3_LOCATION_PREFIX = read_secret("AWS_S3_LOCATION_PREFIX", "dev")

if USE_S3:

    def validate_aws_config():
        """Validate that all required AWS environment variables are set."""
        required_vars = [
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_STORAGE_BUCKET_NAME",
            "AWS_S3_REGION_NAME",
        ]

        missing_vars = [var for var in required_vars if not read_secret(var)]
        if missing_vars:
            raise ImproperlyConfigured(
                f"Missing required AWS environment variables: {', '.join(missing_vars)}"
            )

    validate_aws_config()

    AWS_ACCESS_KEY_ID = read_secret("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = read_secret("AWS_SECRET_ACCESS_KEY")
    AWS_STORAGE_BUCKET_NAME = read_secret("AWS_STORAGE_BUCKET_NAME")
    AWS_S3_REGION_NAME = read_secret("AWS_S3_REGION_NAME")

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
            "BACKEND": "vmlc.storage_backends.PrivateMediaStorage",
        },
        "public": {
            "BACKEND": "vmlc.storage_backends.PublicMediaStorage",
        },
        "staticfiles": {
            "BACKEND": "servestatic.storage.CompressedManifestStaticFilesStorage",
        },
    }
else:
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "servestatic.storage.CompressedManifestStaticFilesStorage",
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
# if read_secret("LOG_QUERIES", "false").lower() == "true":
#     LOGGING["loggers"]["django.db.backends"] = {
#         "level": "DEBUG",
#         "handlers": ["console"],
#         "propagate": False,
#     }
