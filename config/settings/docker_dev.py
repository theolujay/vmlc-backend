# config/settings/docker_dev.py
"""
Docker development settings for the VMLC API project.
This settings configuration is used when running in Docker containers locally.
Uses PostgreSQL container instead of SQLite.
"""

import os
from datetime import timedelta
import dj_database_url
from django.core.exceptions import ImproperlyConfigured

from .base import (  # pylint: disable=unused-import
    AUTH_PASSWORD_VALIDATORS,
    AUTH_USER_MODEL,
    BASE_DIR,
    CELERY_ACCEPT_CONTENT,
    CELERY_RESULT_SERIALIZER,
    CELERY_TASK_SEND_SENT_EVENT,
    CELERY_TASK_SERIALIZER,
    CELERY_TIMEZONE,
    CELERY_WORKER_HIJACK_ROOT_LOGGER,
    CELERY_WORKER_LOG_COLOR,
    CELERY_WORKER_SEND_TASK_EVENTS,
    DEFAULT_AUTO_FIELD,
    INSTALLED_APPS,
    LANGUAGE_CODE,
    MEDIA_ROOT,
    MEDIA_URL,
    MIDDLEWARE,
    REST_FRAMEWORK,
    ROOT_URLCONF,
    SECRET_KEY,
    SIMPLE_JWT,
    STATIC_ROOT,
    STATIC_URL,
    SWAGGER_USE_COMPAT_RENDERERS,
    TEMPLATES,
    TIME_ZONE,
    USE_I18N,
    USE_TZ,
    WSGI_APPLICATION,
)

DEBUG = True

ALLOWED_HOSTS = ["127.0.0.1", "localhost", "0.0.0.0"]

INSTALLED_APPS += [
    "debug_toolbar",
    "django_extensions",
]
MIDDLEWARE += [
    "debug_toolbar.middleware.DebugToolbarMiddleware",
]
INTERNAL_IPS = [
    "127.0.0.1",
]

ADMIN_URL = "admin/"

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:password@db:5432/vmlc_dev"
)
DATABASES = {
    "default": dj_database_url.config(
        default=DATABASE_URL,
        conn_max_age=600,
        conn_health_checks=True,
    )
}

SIMPLE_JWT.update({"ACCESS_TOKEN_LIFETIME": timedelta(days=3)})

# # Docker container logging
# LOG_DIR = Path("/home/app/web/logs")
# LOG_DIR.mkdir(exist_ok=True)

# LOGGING = {
#     "version": 1,
#     "disable_existing_loggers": False,
#     "formatters": {
#         "verbose": {
#             "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
#             "style": "{",
#         },
#     },
#     "handlers": {
#         "console": {
#             "level": "DEBUG",
#             "class": "logging.StreamHandler",
#             "formatter": "verbose",
#         },
#         "file": {
#             "level": "DEBUG",
#             "class": "logging.handlers.RotatingFileHandler",
#             "filename": str(LOG_DIR / "vmlc_api_docker_dev.log"),
#             "formatter": "verbose",
#             "maxBytes": 5 * 1024 * 1024,  # 5MB
#             "backupCount": 3,  # Keep 3 backups
#             "encoding": "utf-8",  # Handle unicode properly
#         },
#     },
#     "loggers": {
#         "api": {
#             "level": "DEBUG",
#             "handlers": ["console", "file"],
#             "propagate": True,
#         },
#     },
# }

CORS_ALLOWED_ORIGINS = ["http://localhost:8000", "http://127.0.0.1:8000"]

GRAPH_MODELS = {
    "all_applications": True,
    "group_models": True,
}

# API Documentation settings
BASE_URL = os.environ.get("BASE_URL")
TOS_URL = os.environ.get("TOS_URL")
CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL")
CONTACT_URL = os.environ.get("CONTACT_URL")
LICENSE_URL = os.environ.get("LICENSE_URL")
LOGO_URL = os.environ.get("LOGO_URL")


# STORAGES = {
#     "default": {
#         "BACKEND": "django.core.files.storage.FileSystemStorage",
#     },
#     "staticfiles": {
#         "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
#     },
# }


# === AWS S3 CONFIGURATION ===
# Validate required AWS environment variables
REQUIRED_AWS_VARS = [
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_STORAGE_BUCKET_NAME",
    "AWS_S3_REGION_NAME",
]

for var in REQUIRED_AWS_VARS:
    if not os.environ.get(var):
        raise ImproperlyConfigured(
            f"The {var} environment variable must be set for S3 storage."
        )

# AWS Configuration
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
AWS_STORAGE_BUCKET_NAME = os.environ.get("AWS_STORAGE_BUCKET_NAME")
AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME")

# S3 Settings
AWS_S3_CUSTOM_DOMAIN = (
    f"{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com"
)
AWS_S3_OBJECT_PARAMETERS = {
    "CacheControl": "max-age=86400",
    "ServerSideEncryption": "AES256",
    "ACL": "bucket-owner-full-control",
}
AWS_S3_VERIFY = True

# Security and performance settings
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

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "dev@vmlc.local"

# Celery Configuration for Docker development
CELERY_BROKER_URL = "redis://redis:6379/0"
CELERY_RESULT_BACKEND = "redis://redis:6379/0"
CELERY_CACHE_BACKEND = "django-cache"

# Redis cache configuration
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://redis:6379/1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}  # remember to run `sudo systemctl start redis-server`

DATA_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024  # 2MB (default is 2.5MB)
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024  # 2MB (default is 2.5MB)
