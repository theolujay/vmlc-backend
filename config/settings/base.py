"""
Base Django settings to be shared across all environments.
"""

from datetime import timedelta
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured
from corsheaders.defaults import default_headers, default_methods
from ._utils import read_secret


BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ============================================================================
# CORE DJANGO SETTINGS
# ============================================================================
SECRET_KEY = read_secret("SECRET_KEY")
DEBUG = str(read_secret("DEBUG", "False")).lower() == "true"

ALLOWED_HOSTS = [
    host.strip() for host in read_secret("ALLOWED_HOSTS", "").split(",") if host.strip()
]
INTERNAL_IPS = [
    ip.strip() for ip in read_secret("INTERNAL_IPS", "").split(",") if ip.strip()
]
ADMIN_URL = read_secret("DJANGO_ADMIN_URL", "admin/")

AUTH_USER_MODEL = "vmlc.User"
APPEND_SLASH = True

INSTALLED_APPS = [
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
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "servestatic.middleware.ServeStaticMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

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

# ============================================================================
# AUTHENTICATION AND PASSWORD VALIDATION
# ============================================================================
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ============================================================================
# INTERNATIONALIZATION
# ============================================================================
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Lagos"
USE_I18N = True
USE_TZ = True

# ============================================================================
# STATIC AND MEDIA FILES
# ============================================================================
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ============================================================================
# STORAGE CONFIGURATION (S3)
# ============================================================================
USE_S3 = str(read_secret("USE_S3", "false")).lower() == "true"

if USE_S3:

    def validate_aws_config():
        required_vars = [
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_STORAGE_BUCKET_NAME",
            "AWS_S3_REGION_NAME",
        ]
        missing_vars = [var for var in required_vars if not read_secret(var)]
        if missing_vars:
            raise ImproperlyConfigured(
                f"Missing required AWS S3 env vars: {', '.join(missing_vars)}"
            )

    validate_aws_config()

    AWS_ACCESS_KEY_ID = read_secret("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = read_secret("AWS_SECRET_ACCESS_KEY")
    AWS_STORAGE_BUCKET_NAME = read_secret("AWS_STORAGE_BUCKET_NAME")
    AWS_S3_REGION_NAME = read_secret("AWS_S3_REGION_NAME")
    AWS_S3_LOCATION_PREFIX = read_secret("AWS_S3_LOCATION_PREFIX", "dev")
    AWS_S3_CUSTOM_DOMAIN = (
        f"{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com"
    )
    AWS_S3_OBJECT_PARAMETERS = {
        "CacheControl": "max-age=86400",
        "ServerSideEncryption": "AES256",
        "ACL": "bucket-owner-full-control",
    }
    AWS_S3_VERIFY = True
    AWS_S3_FILE_OVERWRITE = False
    AWS_QUERYSTRING_AUTH = True
    AWS_QUERYSTRING_EXPIRE = 3600
    AWS_S3_SIGNATURE_VERSION = "s3v4"
    AWS_PRELOAD_METADATA = True
    AWS_S3_MAX_MEMORY_SIZE = 100 * 1024 * 1024

    STORAGES = {
        "default": {"BACKEND": "vmlc.storage_backends.PrivateMediaStorage"},
        "staticfiles": {
            "BACKEND": "servestatic.storage.CompressedManifestStaticFilesStorage"
        },
    }
else:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "servestatic.storage.CompressedManifestStaticFilesStorage"
        },
    }

# ============================================================================
# EMAIL CONFIGURATION
# ============================================================================
EMAIL_BACKEND = read_secret(
    "EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend"
)
EMAIL_HOST = read_secret("EMAIL_HOST")
EMAIL_PORT = int(read_secret("EMAIL_PORT", 587))
EMAIL_HOST_USER = read_secret("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = read_secret("EMAIL_HOST_PASSWORD")
EMAIL_USE_TLS = str(read_secret("EMAIL_USE_TLS", "True")).lower() == "true"
EMAIL_USE_SSL = str(read_secret("EMAIL_USE_SSL", "False")).lower() == "true"
DEFAULT_FROM_EMAIL = read_secret("DEFAULT_FROM_EMAIL", "dev@vmlc.local")
SUPPORT_EMAIL = read_secret("SUPPORT_EMAIL", "verboheitmlc@gmail.com")
SERVER_EMAIL = read_secret("SERVER_EMAIL", "dev@vmlc.local")

EMAIL_TIMEOUT = 30
if DEBUG or SECRET_KEY == "dummy":
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
elif (
    not DEBUG
    and EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend"
    and not all([EMAIL_HOST, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD])
):
    raise ImproperlyConfigured(
        "SMTP email backend requires EMAIL_HOST, EMAIL_HOST_USER, and EMAIL_HOST_PASSWORD to be set in production."
    )

# ============================================================================
# APPLICATION URLS & SERVICE KEYS
# ============================================================================
BASE_URL = read_secret("BASE_URL", "http://localhost:8000")
TOS_URL = read_secret("TOS_URL", f"{BASE_URL}/terms/")
CONTACT_EMAIL = read_secret("CONTACT_EMAIL", "dev@vmlc.local")
CONTACT_URL = read_secret("CONTACT_URL", f"{BASE_URL}/contact/")
LICENSE_URL = read_secret("LICENSE_URL", f"{BASE_URL}/license/")
LOGO_URL = read_secret("LOGO_URL", f"{BASE_URL}/static/images/logo.png")

FRONTEND_BASE_URL = read_secret("FRONTEND_BASE_URL", "http://localhost:3001")
FRONTEND_LOGIN = f"{FRONTEND_BASE_URL}/login/"
FRONTEND_REGISTER_CANDIDATE = f"{FRONTEND_BASE_URL}/register/"
FRONTEND_REGISTER_STAFF = f"{FRONTEND_BASE_URL}/register/staff/"
LANDING_BASE_URL = read_secret("LANDING_BASE_URL", "http://localhost:3000")

TWILIO_ACCOUNT_SID = read_secret("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = read_secret("TWILIO_AUTH_TOKEN")
TWILIO_FROM_PHONE = read_secret("TWILIO_FROM_PHONE")
SLACK_WEBHOOK_URL = read_secret("SLACK_WEBHOOK_URL")
BROADCAST_WEBHOOK_URL = SLACK_WEBHOOK_URL

# ============================================================================
# API, JWT, AND CORS CONFIGURATION
# ============================================================================
REST_FRAMEWORK = {
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/day",
        "user": "1000/day",
        "login": "5/min",
        "burst": "20/min",
        "sustained": "100/hour",
    },
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.NamespaceVersioning",
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    "DEFAULT_PAGINATION_CLASS": "vmlc.pagination.StandardResultsSetPagination",
    "PAGE_SIZE": 20,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(days=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}
SWAGGER_USE_COMPAT_RENDERERS = False

CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in read_secret("CORS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
CORS_ALLOW_CREDENTIALS = (
    str(read_secret("CORS_ALLOW_CREDENTIALS", "false")).lower() == "true"
)
CORS_ALLOW_ALL_ORIGINS = (
    str(read_secret("CORS_ALLOW_ALL_ORIGINS", "false")).lower() == "true"
)
CORS_ALLOW_METHODS = (*default_methods,)
CORS_ALLOW_HEADERS = (*default_headers, "x-api-key")

# ============================================================================
# CHANNELS AND CACHE CONFIGURATION
# ============================================================================
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [
                (
                    read_secret("REDIS_HOST", "127.0.0.1"),
                    int(read_secret("REDIS_PORT", 6379)),
                )
            ]
        },
    },
}

# ============================================================================
# CELERY CONFIGURATION
# ============================================================================
CELERY_TIMEZONE = "Africa/Lagos"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BROKER_URL = read_secret("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = read_secret("CELERY_RESULT_BACKEND", "redis://redis:6379/0")
CELERY_WORKER_SEND_TASK_EVENTS = True
CELERY_TASK_SEND_SENT_EVENT = True
CELERY_WORKER_HIJACK_ROOT_LOGGER = False
CELERY_WORKER_LOG_COLOR = False
CELERY_CACHE_BACKEND = "django-cache"
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_QUEUE_MAX_PRIORITY = 10
CELERY_TASK_DEFAULT_PRIORITY = 5
CELERY_TASK_ROUTES = {
    "send_mail_task": {"queue": "emails", "priority": 9},
    "send_broadcast_task": {"queue": "comms", "priority": 8},
    "send_otp_on_registration_task": {"queue": "emails", "priority": 9},
    "calculate_and_save_auto_score_task": {"queue": "scoring", "priority": 6},
    "validate_user_verification_files_task": {"queue": "files", "priority": 5},
    "generate_leaderboard_snapshot_task": {"queue": "reports", "priority": 3},
    "generate_scores_snapshot_task": {"queue": "reports", "priority": 3},
    "update_staff_dashboard_cache_task": {"queue": "cache", "priority": 2},
    "update_candidate_dashboard_cache_task": {"queue": "cache", "priority": 2},
    "update_candidate_ranking_cache_task": {"queue": "cache", "priority": 2},
}
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_TASK_SOFT_TIME_LIMIT = 300
CELERY_TASK_TIME_LIMIT = 600
CELERY_RESULT_EXPIRES = 3600
CELERY_TASK_IGNORE_RESULT = False

# ============================================================================
# FILE UPLOAD AND MISC SETTINGS
# ============================================================================
DATA_UPLOAD_MAX_MEMORY_SIZE = int(
    read_secret("DATA_UPLOAD_MAX_MEMORY_SIZE", 2 * 1024 * 1024)
)
FILE_UPLOAD_MAX_MEMORY_SIZE = int(
    read_secret("FILE_UPLOAD_MAX_MEMORY_SIZE", 2 * 1024 * 1024)
)

# OpenTelemetry configuration
if read_secret("OTEL_EXPORTER_OTLP_ENDPOINT"):
    from config.otel import configure_opentelemetry

    configure_opentelemetry()
