"""
Base Django settings to be shared across all environments.
"""

import os
from datetime import timedelta
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent.parent


SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("The SECRET_KEY environment variable is not set.")


AUTH_USER_MODEL = "vmlc.User"
APPEND_SLASH = True
# Grouping apps by origin (Django, third-party, local) improves clarity.
INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_api_key",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "django_prometheus",
    "channels",
    "corsheaders",
    "drf_yasg",
    "django_filters",
    "storages",
    "django_celery_results",
    "django_celery_beat",
    "channels",
    "vmlc",
    "comms",
]

MIDDLEWARE = [
    "django_prometheus.middleware.PrometheusBeforeMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_prometheus.middleware.PrometheusAfterMiddleware",
]

PROMETHEUS_LATENCY_BUCKETS = (0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0, 25.0, 50.0, 75.0, float("inf"),)
PROMETHEUS_METRIC_NAMESPACE = "vmlc"
ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {
            "min_length": 8,
        },
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


LANGUAGE_CODE = "en-us"

TIME_ZONE = "Europe/London"

USE_I18N = True

USE_TZ = True


STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Media files (uploads)
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/day",  # Unauthenticated
        "user": "1000/day",  # Authenticated users
        "login": "5/min",  # Login endpoint
        "burst": "20/min",  # For sensitive or POST-heavy endpoints
        "sustained": "100/hour",  # For sustained traffic
    },
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.NamespaceVersioning",
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
    ],
    "DEFAULT_PAGINATION_CLASS": "vmlc.pagination.StandardResultsSetPagination",
    "PAGE_SIZE": 20,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}

SWAGGER_USE_COMPAT_RENDERERS = False

# config/settings/base.py

# ============================================================================
# CELERY CONFIGURATION - Common settings for all environments
# ============================================================================

# Celery Core Settings
CELERY_TIMEZONE = "Europe/London"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# Task Events & Monitoring
CELERY_WORKER_SEND_TASK_EVENTS = True
CELERY_TASK_SEND_SENT_EVENT = True

# Logging Configuration
CELERY_WORKER_HIJACK_ROOT_LOGGER = False
CELERY_WORKER_LOG_COLOR = False  # Can be overridden in dev

# Cache Integration
CELERY_CACHE_BACKEND = "django-cache"

# Queue & Routing Configuration
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_QUEUE_MAX_PRIORITY = 10
CELERY_TASK_DEFAULT_PRIORITY = 5

# Task routing - same for all environments
CELERY_TASK_ROUTES = {
    # HIGH PRIORITY - User-facing tasks
    "send_mail_task": {"queue": "emails", "priority": 9},
    "send_otp_on_registration_task": {"queue": "emails", "priority": 9},
    # MEDIUM PRIORITY - Background processing
    "calculate_and_save_auto_score_task": {"queue": "scoring", "priority": 6},
    "validate_user_verification_files_task": {"queue": "files", "priority": 5},
    # LOW PRIORITY - Administrative tasks
    "generate_leaderboard_snapshot_task": {"queue": "reports", "priority": 3},
    "generate_scores_snapshot_task": {"queue": "reports", "priority": 3},
    "update_staff_dashboard_cache_task": {"queue": "cache", "priority": 2},
    "update_candidate_dashboard_cache_task": {"queue": "cache", "priority": 2},
    "update_candidate_ranking_cache_task": {"queue": "cache", "priority": 2},
}

# Worker Performance Settings
CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # Good for long-running tasks
CELERY_TASK_ACKS_LATE = True  # Don't acknowledge until completion
CELERY_TASK_REJECT_ON_WORKER_LOST = True  # Retry if worker crashes

# Task Time Limits (prevent runaway tasks)
CELERY_TASK_SOFT_TIME_LIMIT = 300  # 5 minutes soft limit
CELERY_TASK_TIME_LIMIT = 600  # 10 minutes hard limit

# Result Settings
CELERY_RESULT_EXPIRES = 3600  # Results expire after 1 hour
CELERY_TASK_IGNORE_RESULT = False  # Keep results for debugging
