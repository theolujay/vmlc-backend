
from .base import *

DEBUG = True

ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

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

# import dj_database_url
# DATABASE_URL = os.environ.get("DATABASE_URL")
# DATABASES = {
#     "default": dj_database_url.config(default=DATABASE_URL, conn_max_age=600)
# }

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

SIMPLE_JWT.update({"ACCESS_TOKEN_LIFETIME": timedelta(days=3)})

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
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
        "file": {
            "level": "DEBUG",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "vmlc_api_dev.log",
            "formatter": "verbose",
            "maxBytes": 5 * 1024 * 1024,  # 5MB
            "backupCount": 3,  # Keep 3 backups
            "encoding": "utf-8",  # Handle unicode properly
        },
    },
    "loggers": {
        "api": {
            "level": "DEBUG",
            "handlers": ["console", "file"],
            "propagate": True,
        },
    },
}


CORS_ALLOWED_ORIGINS = ["http://localhost:8000", "http://127.0.0.1:8000"]

GRAPH_MODELS = {
    "all_applications": True,
    "group_models": True,
}

# API Documentation settings
BASE_URL = "https://example.com"
TOS_URL = "https://example.com/terms/"
CONTACT_EMAIL = "support@example.com"
CONTACT_URL = "https://support.example.com"
LICENSE_URL = "https://example.com/license/"
LOGO_URL = "https://example.com/static/logo.png"

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "no-reply@verboheit.org"

