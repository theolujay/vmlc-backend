"""
Docker Development environment settings.
Used when running in Docker containers locally.
Uses PostgreSQL container and includes comprehensive development tools.
"""

import sys
from datetime import timedelta
import dj_database_url
from dotenv import load_dotenv
from ._utils import read_secret
from .base import *

# Load environment variables from .env file
load_dotenv(BASE_DIR / ".env")

# Ensure SECRET_KEY is set
if not SECRET_KEY:
    raise ValueError("The SECRET_KEY environment variable is not set.")

# ============================================================================
# DOCKER DEVELOPMENT-SPECIFIC SETTINGS
# ============================================================================
DEBUG = True

if "test" not in sys.argv:
    INSTALLED_APPS += ["debug_toolbar", "django_extensions"]
    MIDDLEWARE.insert(
        2, "debug_toolbar.middleware.DebugToolbarMiddleware"
    )  # After CorsMiddleware

# Database configuration for Docker (PostgreSQL with connection pooling)
DATABASE_URL = read_secret(
    "DATABASE_URL",
    f"postgresql://{read_secret('POSTGRES_USER', 'postgres')}:{read_secret('POSTGRES_PASSWORD', 'password')}@db:5432/{read_secret('POSTGRES_DB', 'vmlc_dev')}",
)
db_config = dj_database_url.config(
    default=DATABASE_URL,
    engine="dj_db_conn_pool.backends.postgresql",
    conn_health_checks=True,
)
db_config["POOL_OPTIONS"] = {
    "POOL_SIZE": 5,
    "MAX_OVERFLOW": 10,
    "RECYCLE": 3600,
    "PRE_PING": True,
}
DATABASES = {"default": db_config}

# Increased throttle rates for development
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    "anon": "10000/day",
    "user": "100000/day",
    "login": "500/min",
    "burst": "1000/min",
    "sustained": "1000000/hour",
}

# Extend token lifetimes for easier development
SIMPLE_JWT.update(
    {
        "ACCESS_TOKEN_LIFETIME": timedelta(days=3),
        "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    }
)

ADMINS = [("Olujay", "olujay.dev@gmail.com")]
EMAIL_SUBJECT_PREFIX = "[VMLC DEV] "

# Celery overrides for Docker development
CELERY_WORKER_LOG_COLOR = True
CELERY_TASK_ALWAYS_EAGER = (
    str(read_secret("CELERY_ALWAYS_EAGER", "False")).lower() == "true"
)
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TASK_TRACK_STARTED = True

# Cache configuration for Docker development (Redis)
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
        "KEY_PREFIX": "vmlc_docker_dev",
        "TIMEOUT": 300,
    },
}

# Logging configuration for Docker dev with colored output
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
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
            "formatter": "colored",
        }
    },
    "root": {"level": "WARNING", "handlers": ["console"]},
    "loggers": {
        "vmlc": {"level": "DEBUG", "handlers": ["console"], "propagate": False},
        "comms": {"level": "DEBUG", "handlers": ["console"], "propagate": False},
        "django": {"level": "WARNING", "handlers": ["console"], "propagate": False},
        "celery": {"level": "INFO", "handlers": ["console"], "propagate": False},
        "urllib3": {"level": "ERROR"},
        "requests": {"level": "ERROR"},
        "boto3": {"level": "ERROR"},
        "botocore": {"level": "ERROR"},
        "django.db.backends": {"level": "ERROR"},
        "django.request": {"level": "WARNING"},
        "django.security": {"level": "WARNING"},
    },
}
if str(read_secret("LOG_QUERIES", "false")).lower() == "true":
    LOGGING["loggers"]["django.db.backends"]["level"] = "DEBUG"
if str(read_secret("LOG_REQUESTS", "false")).lower() == "true":
    LOGGING["loggers"]["django.request"]["level"] = "INFO"

# Django Debug Toolbar configuration
DEBUG_TOOLBAR_CONFIG = {
    "SHOW_TOOLBAR_CALLBACK": lambda request: DEBUG,
    "INTERCEPT_REDIRECTS": False,
}
GRAPH_MODELS = {"all_applications": True, "group_models": True}

# Relaxed security settings for Docker development
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
