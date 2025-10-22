"""
Test environment for CI/CD pipelines.
"""

import dj_database_url

from .base import *

SECRET_KEY = "this-is-a-test-secret-key--do-not-use-in-production"
if not SECRET_KEY:
    raise ValueError("The SECRET_KEY environment variable is not set.")

from .base import *
DEBUG = False
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

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_URL = 'memory://'  # Use in-memory broker for tests
CELERY_RESULT_BACKEND = 'cache+memory://'  # Use in-memory results

AWS_ACCESS_KEY_ID = "test-access-key"
AWS_SECRET_ACCESS_KEY = "test-secret-key"
AWS_STORAGE_BUCKET_NAME = "test-bucket"
AWS_S3_REGION_NAME = "us-west-2"

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
SUPPORT_EMAIL = "verboheitmlc@gmail.com"