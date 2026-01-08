"""
Local development environment settings.
This settings configuration is used when running without Docker containers locally.
Uses SQLite by default, but can be configured to use NeonDB.
"""

import sys
from datetime import timedelta
import dj_database_url
from dotenv import load_dotenv
from .base import *
from ._utils import read_secret


# Load environment variables from .env file
load_dotenv(BASE_DIR / ".env")

# Ensure SECRET_KEY is set
if not SECRET_KEY:
    raise ValueError("The SECRET_KEY environment variable is not set.")

# ============================================================================
# DEVELOPMENT-SPECIFIC SETTINGS
# ============================================================================
DEBUG = True

if "test" not in sys.argv:
    INSTALLED_APPS += [
        "debug_toolbar",
        "django_extensions",
    ]
    MIDDLEWARE.insert(
        2, "debug_toolbar.middleware.DebugToolbarMiddleware"
    )  # After CorsMiddleware

# Use NeonDB if URL is provided, otherwise default to SQLite
DATABASES = {
    "default": dj_database_url.parse(
        read_secret("DATABASE_URL", f"sqlite:///{BASE_DIR / 'db.sqlite3'}")
    )
}

# Extend token lifetimes for easier development
SIMPLE_JWT.update(
    {
        "ACCESS_TOKEN_LIFETIME": timedelta(days=3),
        "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    }
)

# Celery settings for local development
CELERY_WORKER_LOG_COLOR = True
CELERY_TASK_ALWAYS_EAGER = False
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_WORKER_CONCURRENCY = 2

# Cache configuration for development (local Redis)
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://localhost:6379/1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "CONNECTION_POOL_KWARGS": {
                "retry_on_timeout": True,
                "health_check_interval": 30,
            },
        },
        "KEY_PREFIX": "vmlc_dev_sync",
        "TIMEOUT": 300,
    },
    "async": {
        "BACKEND": "django_async_redis.cache.RedisCache",
        "LOCATION": "redis://localhost:6379/2",
        "OPTIONS": {"CLIENT_CLASS": "django_async_redis.client.DefaultClient"},
        "KEY_PREFIX": "vmlc_dev_async",
        "TIMEOUT": 300,
    },
}

# Logging for development
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "{levelname} {asctime} {module}: {message}", "style": "{"}
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        }
    },
    "loggers": {
        "vmlc": {"level": "DEBUG", "handlers": ["console"], "propagate": True},
        "comms": {"level": "DEBUG", "handlers": ["console"], "propagate": True},
        "django.db.backends": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
    },
}

# Django Debug Toolbar configuration
DEBUG_TOOLBAR_CONFIG = {
    "SHOW_TOOLBAR_CALLBACK": lambda request: DEBUG,
    "INTERCEPT_REDIRECTS": False,
}

# Define panels to exclude RequestPanel due to async incompatibility (SynchronousOnlyOperation)
DEBUG_TOOLBAR_PANELS = [
    "debug_toolbar.panels.history.HistoryPanel",
    "debug_toolbar.panels.versions.VersionsPanel",
    "debug_toolbar.panels.timer.TimerPanel",
    "debug_toolbar.panels.settings.SettingsPanel",
    "debug_toolbar.panels.headers.HeadersPanel",
    "debug_toolbar.panels.sql.SQLPanel",
    "debug_toolbar.panels.staticfiles.StaticFilesPanel",
    "debug_toolbar.panels.templates.TemplatesPanel",
    "debug_toolbar.panels.cache.CachePanel",
    "debug_toolbar.panels.signals.SignalsPanel",
    "debug_toolbar.panels.logging.LoggingPanel",
    "debug_toolbar.panels.redirects.RedirectsPanel",
    "debug_toolbar.panels.profiling.ProfilingPanel",
]

# Django Extensions graph models configuration
GRAPH_MODELS = {"all_applications": True, "group_models": True}

# Less restrictive security settings for development
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Session settings for development
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
