"""
Production environment settings.
"""

import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv
from corsheaders.defaults import default_headers, default_methods
from django.core.exceptions import ImproperlyConfigured
import warnings

warnings.filterwarnings("ignore", category=RuntimeWarning, module="pycparser")
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / "prod.env")

from .base import *

DEBUG = os.getenv("DEBUG").lower() == "true"

# === SECURITY SETTINGS ===
INTERNAL_IPS = [
    ip.strip() for ip in os.getenv("INTERNAL_IPS", "").split(",") if ip.strip()
]

ALLOWED_HOSTS = [
    host.strip() for host in os.getenv("ALLOWED_HOSTS", "").split(",") if host.strip()
]

ADMIN_URL = os.getenv("DJANGO_ADMIN_URL", "admin/")

# === DATABASE CONFIG ===
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ImproperlyConfigured("DATABASE_URL environment variable is required")

DATABASES = {
    "default": dj_database_url.config(
        default=DATABASE_URL,
        conn_max_age=600,
        conn_health_checks=True,
    )
}

REQUIRED_AWS_VARS = [
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_STORAGE_BUCKET_NAME",
    "AWS_S3_REGION_NAME",
]

for var in REQUIRED_AWS_VARS:
    if not os.getenv(var):
        raise ImproperlyConfigured(
            f"The {var} environment variable must be set for S3 storage."
        )

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

# === LOGGING CONFIGURATION ===
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "skip_static_requests": {
            "()": "django.utils.log.CallbackFilter",
            "callback": lambda record: not (
                "GET /static/" in record.getMessage() and record.args[1] == "200"
            ),
        }
    },
    "formatters": {
        # "verbose": {
        #     "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
        #     "style": "{",
        # },
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(name)s %(levelname)s %(module)s %(lineno)d %(message)s",
        },
        "access": {
            "format": "%(message)s",
        },
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
        "access_console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "access",
            "filters": ["skip_static_requests"],
        },
    },
    "root": {
        "level": "INFO",
        "handlers": ["console"],
    },
    "loggers": {
        "vmlc": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
        "comms": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
        "celery": {
            "level": "ERROR",
            "handlers": ["console"],
            "propagate": False,
        },
        "django": {
            "level": "WARNING",
            "handlers": ["console"],
            "propagate": False,
        },
        "django.request": {
        "level": "ERROR",
        "handlers": ["console"],
        "propagate": False,
    },
        "gunicorn.access": {
            "level": "INFO",
            "handlers": ["access_console"],
            "propagate": False,
        },
    },
}

# === CORS CONFIGURATION ===
cors_origins = os.getenv("CORS_ALLOWED_ORIGINS", "")
if cors_origins:
    CORS_ALLOWED_ORIGINS = [
        origin.strip() for origin in cors_origins.split(",") if origin.strip()
    ]
else:
    CORS_ALLOWED_ORIGINS = []

CORS_ALLOW_CREDENTIALS = os.environ.get("CORS_ALLOW_CREDENTIALS", "false").lower() == "true"
CORS_ALLOW_ALL_ORIGINS = os.environ.get("CORS_ALLOW_ALL_ORIGINS", "false").lower() == "true"
CORS_ALLOW_METHODS = (
    *default_methods,
)

CORS_ALLOW_HEADERS = (
    *default_headers,
    "x-api-key",
)

# === EMAIL CONFIGURATION ===
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() == "true"
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL")

if EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend":
    required_email_vars = [
        EMAIL_HOST,
        EMAIL_HOST_USER,
        EMAIL_HOST_PASSWORD,
        DEFAULT_FROM_EMAIL,
    ]
    if not all(required_email_vars):
        raise ImproperlyConfigured(
            "When using SMTP email backend, you must set EMAIL_HOST, EMAIL_HOST_USER, "
            "EMAIL_HOST_PASSWORD, and DEFAULT_FROM_EMAIL environment variables."
        )

# === APPLICATION URLS ===
BASE_URL = os.getenv("BASE_URL")
TOS_URL = os.getenv("TOS_URL")
CONTACT_EMAIL = os.getenv("CONTACT_EMAIL")
CONTACT_URL = os.getenv("CONTACT_URL")
LICENSE_URL = os.getenv("LICENSE_URL")
# === REDIS CONFIGURATION ===
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
CACHE_REDIS_URL = os.getenv("CACHE_REDIS_URL", "redis://redis:6379/1")
# ============================================================================
# CELERY CONFIGURATION - Production Environment
# ============================================================================

# Production Redis (AWS ElastiCache, etc.)
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0")

# Production-specific overrides
CELERY_WORKER_LOG_COLOR = False  # No colors in production logs
CELERY_TASK_ALWAYS_EAGER = False  # Never use eager mode in production
CELERY_TASK_EAGER_PROPAGATES = False

# Optimized for 8GB/2vCPU VPS with production + staging
CELERY_WORKER_CONCURRENCY = 2  # Match available vCPUs (was 8)
CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000  # Keep as-is
CELERY_WORKER_MAX_MEMORY_PER_CHILD = 300000  # ~300MB (was 200MB, you have 768MB limit)

# Production monitoring and reliability
CELERY_TASK_TRACK_STARTED = True
CELERY_SEND_TASK_EVENTS = True
CELERY_WORKER_SEND_TASK_EVENTS = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True

# Keep time limits
CELERY_TASK_SOFT_TIME_LIMIT = 120
CELERY_TASK_TIME_LIMIT = 300  # Increased to 5min (you set --time-limit=300 in compose)

# Optimized broker settings
CELERY_BROKER_TRANSPORT_OPTIONS = {
    "visibility_timeout": 1800,  # 30min (reduced from 1hr, faster retry)
    "fanout_prefix": True,
    "fanout_patterns": True,
}

# Shorter result expiry to save Redis memory
CELERY_RESULT_EXPIRES = 900  # 15 minutes (was 30, Redis is only 192MB)

# ============================================================================
# CACHE CONFIGURATION - Production Environment
# ============================================================================
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": [
            os.getenv("CACHE_REDIS_URL"),
        ],
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "CONNECTION_POOL_KWARGS": {
                "retry_on_timeout": True,
                "health_check_interval": 60,
                "socket_connect_timeout": 3,
                "socket_timeout": 3,
                "max_connections": 20,
            },
            "COMPRESSOR": "django_redis.compressors.zlib.ZlibCompressor",
            "SERIALIZER": "django_redis.serializers.json.JSONSerializer",
        },
        "KEY_PREFIX": "vmlc_prod",
        "TIMEOUT": 600,
    },
}

# === PERFORMANCE OPTIMIZATIONS ===
# Enable persistent database connections
CONN_MAX_AGE = 600

# Security headers
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True

# HSTS - Make browsers stick to HTTPS
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SAMESITE = "Lax"
# === FILE UPLOAD SETTINGS ===
# Increase file upload limits if needed
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024  # 2MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024  # 2MB
DATA_UPLOAD_MAX_NUMBER_FIELDS = 1000

# Maximum file sizes for different upload types
FILE_UPLOAD_PERMISSIONS = 0o644
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o755
