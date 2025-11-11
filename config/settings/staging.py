"""
Staging environment settings.
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
load_dotenv(BASE_DIR / "staging.env")

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

DEBUG = read_secret("DEBUG").lower() == "true"

# === SECURITY SETTINGS ===
INTERNAL_IPS = [
    ip.strip() for ip in read_secret("INTERNAL_IPS", "").split(",") if ip.strip()
]

ALLOWED_HOSTS = [
    host.strip() for host in read_secret("ALLOWED_HOSTS", "").split(",") if host.strip()
]

ADMIN_URL = read_secret("DJANGO_ADMIN_URL", "admin/")

# === DATABASE CONFIG ===
DATABASE_URL = read_secret("DATABASE_URL")
if not DATABASE_URL:
    raise ImproperlyConfigured("DATABASE_URL environment variable is required")

db_config = dj_database_url.config(
        default=DATABASE_URL,
        engine="dj_db_conn_pool.backends.postgresql",
        conn_health_checks=True,
    )

db_config['POOL_OPTIONS'] = {
    'POOL_SIZE': 3,
    'MAX_OVERFLOW': 5,
    'RECYCLE': 3600,
    'PRE_PING': True,
}

db_config.pop('CONN_MAX_AGE', None)

DATABASES = {
    "default": db_config
}

REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    "anon": "1000/day",  # Unauthenticated
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


# === AWS S3 CONFIGURATION ===
REQUIRED_AWS_VARS = [
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_STORAGE_BUCKET_NAME",
    "AWS_S3_REGION_NAME",
]

for var in REQUIRED_AWS_VARS:
    if not read_secret(var):
        raise ImproperlyConfigured(
            f"The {var} environment variable must be set for S3 storage."
        )

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
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
        "django": {
            "level": "WARNING",
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
cors_origins = read_secret("CORS_ALLOWED_ORIGINS", "")
if cors_origins:
    CORS_ALLOWED_ORIGINS = [
        origin.strip() for origin in cors_origins.split(",") if origin.strip()
    ]
else:
    CORS_ALLOWED_ORIGINS = []

CORS_ALLOW_CREDENTIALS = read_secret("CORS_ALLOW_CREDENTIALS", "false").lower() == "true"
CORS_ALLOW_ALL_ORIGINS = read_secret("CORS_ALLOW_ALL_ORIGINS", "false").lower() == "true"
CORS_ALLOW_METHODS = (
    *default_methods,
)

CORS_ALLOW_HEADERS = (
    *default_headers,
    "x-api-key",
)

# === EMAIL CONFIGURATION ===
EMAIL_BACKEND = read_secret("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = read_secret("EMAIL_HOST")
EMAIL_PORT = int(read_secret("EMAIL_PORT", "587"))
EMAIL_USE_TLS = read_secret("EMAIL_USE_TLS", "True").lower() == "true"
EMAIL_HOST_USER = read_secret("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = read_secret("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = read_secret("DEFAULT_FROM_EMAIL")

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
BASE_URL = read_secret("BASE_URL")
TOS_URL = read_secret("TOS_URL")
CONTACT_EMAIL = read_secret("CONTACT_EMAIL")
CONTACT_URL = read_secret("CONTACT_URL")
LICENSE_URL = read_secret("LICENSE_URL")
# === REDIS CONFIGURATION ===
REDIS_URL = read_secret("REDIS_URL", "redis://redis:6379/0")
CACHE_REDIS_URL = read_secret("CACHE_REDIS_URL", "redis://redis:6379/1")
# ============================================================================
# CELERY CONFIGURATION - Staging Environment
# ============================================================================

CELERY_BROKER_URL = read_secret("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = read_secret("CELERY_RESULT_BACKEND", "redis://redis:6379/0")

# Staging-specific overrides
CELERY_WORKER_LOG_COLOR = False  # No colors in staging logs
CELERY_TASK_ALWAYS_EAGER = False  # Always use real async processing
CELERY_TASK_EAGER_PROPAGATES = False  # Don't propagate in staging

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
# CACHE CONFIGURATION - Staging Environment
# ============================================================================
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": [
            read_secret("CACHE_REDIS_URL"),
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
        "KEY_PREFIX": "vmlc_staging",
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
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB

# Maximum file sizes for different upload types
FILE_UPLOAD_PERMISSIONS = 0o644
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o755

FRONTEND_BASE_URL = read_secret("FRONTEND_BASE_URL", "https://staging-portal.verboheit.org")
FRONTEND_LOGIN = FRONTEND_BASE_URL + "/login/"
FRONTEND_REGISTER_CANDIDATE = FRONTEND_BASE_URL + "/register/"
FRONTEND_REGISTER_STAFF = FRONTEND_BASE_URL + "/register/staff/"
SUPPORT_EMAIL = read_secret("SUPPORT_EMAIL", "verboheitmlc@gmail.com")