"""
Staging environment settings.
"""

import os
from datetime import timedelta
import dj_database_url
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured
from ._utils import read_secret
from .base import *

# Load environment variables from staging.env file
load_dotenv(BASE_DIR / "staging.env")
# Ensure SECRET_KEY is set for staging
if not SECRET_KEY:
    raise ValueError("The SECRET_KEY environment variable must be set in staging.")

# ============================================================================
# STAGING-SPECIFIC SETTINGS
# ============================================================================

# === DATABASE CONFIGURATION ===
DATABASE_URL = read_secret("DATABASE_URL")
if not DATABASE_URL:
    raise ImproperlyConfigured(
        "DATABASE_URL environment variable is required for staging."
    )

db_config = dj_database_url.config(
    default=DATABASE_URL,
    engine="dj_db_conn_pool.backends.postgresql",
    conn_health_checks=True,
)
db_config["POOL_OPTIONS"] = {
    "POOL_SIZE": 3,
    "MAX_OVERFLOW": 5,
    "RECYCLE": 3600,
    "PRE_PING": True,
}
DATABASES = {"default": db_config}

# === S3 CONFIGURATION ===
# Explicitly set USE_S3 to True for staging since it's required for media storage.
USE_S3 = True
# AWS S3 Location Prefix for staging
AWS_S3_LOCATION_PREFIX = read_secret("AWS_S3_LOCATION_PREFIX", "staging")

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

# === API AND JWT OVERRIDES ===
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"].update(
    {
        "anon": "1000/day",
        "user": "100000/day",
        "login": "500/min",
        "burst": "1000/min",
        "sustained": "1000000/hour",
    }
)
SIMPLE_JWT.update(
    {
        "ACCESS_TOKEN_LIFETIME": timedelta(days=3),
        "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    }
)

# === LOGGING CONFIGURATION ===
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "skip_static_requests": {
            "()": "django.utils.log.CallbackFilter",
            "callback": lambda r: "GET /static/" not in r.getMessage(),
        }
    },
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(name)s %(levelname)s %(module)s %(lineno)d %(message)s",
        },
        "access": {"format": "%(message)s"},
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
    "root": {"level": "INFO", "handlers": ["console"]},
    "loggers": {
        "vmlc": {"level": "WARNING", "handlers": ["console"], "propagate": False},
        "comms": {"level": "WARNING", "handlers": ["console"], "propagate": False},
        "celery": {"level": "WARNING", "handlers": ["console"], "propagate": False},
        "django": {"level": "WARNING", "handlers": ["console"], "propagate": False},
        "gunicorn.access": {
            "level": "INFO",
            "handlers": ["access_console"],
            "propagate": False,
        },
    },
}

# === OPENTELEMETRY ===
if (
    str(
        read_secret("OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED", "false")
    ).lower()
    == "true"
):
    from opentelemetry.instrumentation.logging import LoggingInstrumentor
    import logging

    try:
        LoggingInstrumentor().instrument(set_logging_format=True)
        logging.getLogger(__name__).info(
            "OpenTelemetry logging instrumentation initialized."
        )
    except Exception as e:
        logging.getLogger(__name__).error(
            f"Failed to initialize OpenTelemetry logging: {e}"
        )

# === CELERY CONFIGURATION ===
CELERY_WORKER_LOG_COLOR = False
CELERY_TASK_ALWAYS_EAGER = False
CELERY_TASK_EAGER_PROPAGATES = False
CELERY_WORKER_CONCURRENCY = 2
CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000
CELERY_WORKER_MAX_MEMORY_PER_CHILD = 300000
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_TASK_SOFT_TIME_LIMIT = 120
CELERY_TASK_TIME_LIMIT = 300
CELERY_BROKER_TRANSPORT_OPTIONS = {
    "visibility_timeout": 1800,
    "fanout_prefix": True,
    "fanout_patterns": True,
}
CELERY_RESULT_EXPIRES = 900

# === CACHE CONFIGURATION ===
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": read_secret("CACHE_REDIS_URL"),
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

# === PERFORMANCE & SECURITY ===
CONN_MAX_AGE = 600
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SAMESITE = "Lax"

# === FILE UPLOAD SETTINGS ===
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
DATA_UPLOAD_MAX_NUMBER_FIELDS = 1000
FILE_UPLOAD_PERMISSIONS = 0o644
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o755
