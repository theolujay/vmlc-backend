"""
Production settings for the VMLC API project.
These settings are used in the production environment and should not be used in development."""

from .base import *
import dj_database_url
from django.core.exceptions import ImproperlyConfigured

DEBUG = False

INTERNAL_IPS = [
    ip.strip()
    for ip in os.environ.get("INTERNAL_IPS").split(",")
]

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("ALLOWED_HOSTS", "").split(",")
    if host.strip()
]


ADMIN_URL = os.environ.get("DJANGO_ADMIN_URL")
DATABASE_URL = os.environ.get("DATABASE_URL")
DATABASES = {
    "default": dj_database_url.config(default=DATABASE_URL, conn_max_age=600)
}

LOG_DIR = Path("/home/app/web/logs")
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
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "vmlc_api.log"),
            "formatter": "verbose",
            "maxBytes": 5 * 1024 * 1024,  # 5MB
            "backupCount": 3,  # Keep 3 backups
            "encoding": "utf-8",  # Handle unicode properly
        },
    },
    "loggers": {
        "api": {
            "level": "INFO",
            "handlers": ["console", "file"],
            "propagate": True,
        },
    },
}


CORS_ALLOWED_ORIGINS = os.environ.get("CORS_ALLOWED_ORIGINS").split(",")

# API Documentation settings
BASE_URL = os.environ.get("BASE_URL")
TOS_URL = os.environ.get("TOS_URL")
CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL")
CONTACT_URL = os.environ.get("CONTACT_URL")
LICENSE_URL = os.environ.get("LICENSE_URL")
LOGO_URL = os.environ.get("LOGO_URL")

for var in [
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_STORAGE_BUCKET_NAME",
    "AWS_S3_REGION_NAME",
]:
    if not os.environ.get(var):
        raise ValueError(
            f"The {var} environment variable must be set for S3 storage."
        )

AWS_STORAGE_BUCKET_NAME = os.environ.get("AWS_STORAGE_BUCKET_NAME")
AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME")
AWS_S3_CUSTOM_DOMAIN = (
    f"{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com"
)

STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        "OPTIONS": {
            "bucket_name": AWS_STORAGE_BUCKET_NAME,
            "region_name": AWS_S3_REGION_NAME,
            "custom_domain": AWS_S3_CUSTOM_DOMAIN,
        },
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.StaticFilesStorage",
    },
}


EMAIL_BACKEND = (
    "django.core.mail.backends.smtp.EmailBackend"
)
EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL")
if EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend" and not all(
    [EMAIL_HOST, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD]
):
    raise ImproperlyConfigured(
        "When using the SMTP email backend, you must set EMAIL_HOST, EMAIL_HOST_USER, and EMAIL_HOST_PASSWORD in your .env file."
    )
    
