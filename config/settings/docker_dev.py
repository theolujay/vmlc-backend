"""
Docker Development environment settings
Used when running in Docker containers locally.
Uses PostgreSQL container and includes comprehensive development tools.
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
    file_path = os.getenv(f'{secret_name}_FILE')
    if file_path and os.path.exists(file_path):
        with open(file_path, 'r') as f:
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

if 'test' not in sys.argv:
    INSTALLED_APPS += [
        "debug_toolbar",
        "django_extensions",
        # "silk",  # SQL profiling
    ]
    MIDDLEWARE += [
        "debug_toolbar.middleware.DebugToolbarMiddleware",
        # "silk.middleware.SilkyMiddleware",
    ]

ADMIN_URL = read_secret("DJANGO_ADMIN_URL", "admin/")

DATABASE_URL = read_secret(
    "DATABASE_URL",
    f"postgresql://{read_secret('POSTGRES_USER', 'postgres')}:"
    f"{read_secret('POSTGRES_PASSWORD', 'password')}@"
    f"db:5432/{read_secret('POSTGRES_DB', 'vmlc_dev')}",
)

db_config = dj_database_url.config(
        default=DATABASE_URL,
        engine="dj_db_conn_pool.backends.postgresql",
        conn_health_checks=True,
    )

db_config['POOL_OPTIONS'] = {
    'POOL_SIZE': 5,
    'MAX_OVERFLOW': 10,
    'RECYCLE': 3600,
    'PRE_PING': True,
}

db_config.pop('CONN_MAX_AGE', None)

DATABASES = {
    "default": db_config
}

REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    "anon": "10000/day",  # Unauthenticated
    "user": "100000/day",  # Authenticated users
    "login": "500/min",  # Login endpoint
    "burst": "1000/min",  # For sensitive or POST-heavy endpoints
    "sustained": "1000000/hour",  # For sustained traffic
}

SIMPLE_JWT.update(
    {
        "ACCESS_TOKEN_LIFETIME": timedelta(days=3),
        "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
        "ROTATE_REFRESH_TOKENS": True,
    }
)

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8000",
    "http://localhost:5173",
]

CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "x-api-key",
]

ADMINS = [
    ("Olujay", "olujay.dev@gmail.com"),
    # ("Verboheit Consulting", "verboheitconsulting@gmail.com"),
]

EMAIL_SUBJECT_PREFIX = "[VMLC Portal]"
SERVER_EMAIL = read_secret("SERVER_EMAIL", "dev@vmlc.local")

BROADCAST_WEBHOOK_URL = read_secret("BROADCAST_WEBHOOK_URL", "https://discord.com/api/webhooks/1370874847856562217/LkstQ0YyZrqE_Unp01TxT2tYvChJvc0E-DXzUNp5sm1pa7GPq_1ERj67R5ZL96Dh1S0N")

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
# EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = read_secret("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(read_secret("EMAIL_PORT", "587"))
EMAIL_HOST_USER = read_secret("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = read_secret("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = True  # ← Enable TLS for Gmail port 587
EMAIL_USE_SSL = False  # ← Keep SSL disabled when using TLS
DEFAULT_FROM_EMAIL = read_secret("DEFAULT_FROM_EMAIL", "test@verboheit.dev")

# Fallback to console if no EMAIL_HOST is provided
# if not read_secret("EMAIL_HOST"):
#     EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

BASE_URL = read_secret("BASE_URL", "http://localhost:8000")
TOS_URL = read_secret("TOS_URL", f"{BASE_URL}/terms/")
CONTACT_EMAIL = read_secret("CONTACT_EMAIL", "dev@vmlc.local")
CONTACT_URL = read_secret("CONTACT_URL", f"{BASE_URL}/contact/")
LICENSE_URL = read_secret("LICENSE_URL", f"{BASE_URL}/license/")
LOGO_URL = read_secret("LOGO_URL", f"{BASE_URL}/static/images/logo.png")


# ============================================================================
# CELERY CONFIGURATION - Docker Development Environment
# ============================================================================

# Docker service names for Redis broker
CELERY_BROKER_URL = read_secret("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = read_secret("CELERY_RESULT_BACKEND", "redis://redis:6379/0")

# Docker development overrides
CELERY_WORKER_LOG_COLOR = True  # Enable colored logs
CELERY_TASK_ALWAYS_EAGER = read_secret("CELERY_ALWAYS_EAGER", "False").lower() == "true"
CELERY_TASK_EAGER_PROPAGATES = True

# Development debugging
CELERY_TASK_TRACK_STARTED = True  # Track when tasks start
CELERY_SEND_TASK_EVENTS = True  # Send task events for monitoring

# ============================================================================
# CACHE CONFIGURATION - Docker Development Environment
# ============================================================================

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": read_secret("CACHE_REDIS_URL", "redis://redis:6379/1"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "CONNECTION_POOL_KWARGS": {
                "retry_on_timeout": True,
                "health_check_interval": 30,
                "socket_connect_timeout": 5,
                "socket_timeout": 5,
            },
            "COMPRESSOR": "django_redis.compressors.zlib.ZlibCompressor",
            "SERIALIZER": "django_redis.serializers.json.JSONSerializer",
        },
        "KEY_PREFIX": "vmlc_docker_dev_sync",
        "TIMEOUT": 300,
    },
}

USE_S3 = read_secret("USE_S3", "false").lower() == "true"

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
            # "formatter": "colored" if read_secret("USE_COLORED_LOGS", "true").lower() == "true" else "simple",
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
        "django.request": {"level": "WARNING"},  # Log 4xx responses
        "django.security": {"level": "WARNING"},  # Security warnings only
        # "asyncio": {"level": "WARNING"},        # Async noise reduction
    },
}

if read_secret("LOG_QUERIES", "false").lower() == "true":
    LOGGING["loggers"]["django.db.backends"]["level"] = "DEBUG"

# Enable request logging for debugging
if read_secret("LOG_REQUESTS", "false").lower() == "true":
    LOGGING["loggers"]["django.request"]["level"] = "INFO"

DATA_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024  # 2MB for development
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024  # 2MB for development

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

# Security settings (safe to enable in dev)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True  # Optional, adds X-XSS-Protection header

# These are technically "HTTPS-only" settings
# Setting them True in dev won't break anything if you don't test cookies over HTTP
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# HSTS (leave very low so you don't lock yourself out of localhost)
SECURE_HSTS_SECONDS = 0  # Means it's effectively disabled, but no warning
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

FRONTEND_BASE_URL = read_secret("FRONTEND_BASE_URL", "https://dev-portal.verboheit.org")
SUPPORT_EMAIL = read_secret("SUPPORT_EMAIL", "verboheitmlc@gmail.com")