# config/settings/docker_dev.py
"""
Docker development settings for the VMLC API project.
These settings are used when running the application in Docker containers locally.
Uses PostgreSQL container instead of SQLite.
"""

from .base import *
import dj_database_url

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

# Use PostgreSQL container instead of SQLite
DATABASE_URL = os.environ.get(
    "DATABASE_URL", 
    "postgresql://postgres:password@db:5432/vmlc_dev"
)
DATABASES = {
    "default": dj_database_url.config(default=DATABASE_URL, conn_max_age=600)
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


STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "dev@vmlc.local"

# Celery Configuration for Docker development
CELERY_BROKER_URL = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
CELERY_CACHE_BACKEND = 'django-cache'

# Redis cache configuration
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL', 'redis://redis:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}