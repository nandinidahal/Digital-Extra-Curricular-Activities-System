"""
Django settings for the Digital Extra-Curricular Activities System (DEAS).

All secrets and environment-specific values come from environment variables.
Locally they are loaded from a `.env` file (never commit it). In production,
set real environment variables on the server instead.
"""
import os
from datetime import timedelta
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


# --------------------------------------------------------------------------
# Small helpers for reading environment variables
# --------------------------------------------------------------------------
def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name, default):
    value = os.environ.get(name)
    return int(value) if value not in (None, "") else default


def env_list(name, default=""):
    raw = os.environ.get(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


# --------------------------------------------------------------------------
# Core
# --------------------------------------------------------------------------
DEBUG = env_bool("DJANGO_DEBUG", False)

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY is not set. Copy .env.example to .env and set a "
        "long random value."
    )
if not DEBUG and SECRET_KEY.startswith("change-me"):
    raise ImproperlyConfigured("Set a real DJANGO_SECRET_KEY before running in production.")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1" if DEBUG else "")

INSTALLED_APPS = [
    # daphne must come before django.contrib.staticfiles so `runserver` serves
    # HTTP *and* WebSockets through ASGI (config/asgi.py).
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "channels",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",  # enables refresh-token blacklisting
    "corsheaders",
    # Local apps
    "common",
    "accounts",
    "profiles",
    "friends",
    "social",
    "messaging",
    "announcements",
    "achievements",
    "notifications",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",  # must be above CommonMiddleware
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


# --------------------------------------------------------------------------
# Database (PostgreSQL)
# --------------------------------------------------------------------------
if os.environ.get("DB_ENGINE", "postgresql").lower() == "sqlite":
    # Only for quick local experiments. Use PostgreSQL for real work.
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DB_NAME", "deas_db"),
            "USER": os.environ.get("DB_USER", "postgres"),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ.get("DB_HOST", "localhost"),
            "PORT": os.environ.get("DB_PORT", "5432"),
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# --------------------------------------------------------------------------
# Authentication
# --------------------------------------------------------------------------
# IMPORTANT: this must be set BEFORE the very first `migrate`.
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --------------------------------------------------------------------------
# Django REST Framework
# --------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    # Secure by default: every view needs a valid access token unless it
    # explicitly opts out with `permission_classes = [AllowAny]`.
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_RENDERER_CLASSES": (
        ["rest_framework.renderers.JSONRenderer"]
        + (["rest_framework.renderers.BrowsableAPIRenderer"] if DEBUG else [])
    ),
    "DEFAULT_PARSER_CLASSES": ("rest_framework.parsers.JSONParser",),
    "EXCEPTION_HANDLER": "accounts.exceptions.api_exception_handler",
    # Number of reverse proxies in front of Django. 0 = use REMOTE_ADDR.
    # Needed so throttling sees the real client IP and cannot be spoofed.
    "NUM_PROXIES": env_int("NUM_PROXIES", 0),
}

# Rates for the custom throttles in accounts/throttles.py.
# Format: "<count>/<sec|min|hour|day>"
AUTH_THROTTLE_RATES = {
    "register": "10/hour",
    "login": "30/min",
    "login_email": "20/hour",
    "otp_verify": "20/min",
    "otp_request_ip": "20/hour",
    "otp_request_email": "5/hour",
    "otp_request_email_burst": "1/min",
    "password_reset": "20/hour",
    "token_refresh": "60/min",
    "password_change": "10/hour",
}


# --------------------------------------------------------------------------
# JWT (djangorestframework-simplejwt)
# --------------------------------------------------------------------------
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env_int("JWT_ACCESS_MINUTES", 15)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env_int("JWT_REFRESH_DAYS", 7)),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": False,  # we update last_login ourselves on /login/
    "ALGORITHM": "HS256",
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}


# --------------------------------------------------------------------------
# Accounts module settings
# --------------------------------------------------------------------------
OTP_LENGTH = 6
OTP_VALID_MINUTES = env_int("OTP_VALID_MINUTES", 5)
OTP_MAX_ATTEMPTS = env_int("OTP_MAX_ATTEMPTS", 5)
OTP_RESEND_COOLDOWN_SECONDS = env_int("OTP_RESEND_COOLDOWN_SECONDS", 60)
OTP_MAX_REQUESTS_PER_HOUR = env_int("OTP_MAX_REQUESTS_PER_HOUR", 5)
PASSWORD_RESET_TOKEN_MINUTES = env_int("PASSWORD_RESET_TOKEN_MINUTES", 10)
MINIMUM_USER_AGE = env_int("MINIMUM_USER_AGE", 13)


# --------------------------------------------------------------------------
# Email (real SMTP delivery)
# --------------------------------------------------------------------------
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = env_int("EMAIL_PORT", 587)
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_TIMEOUT = 10  # seconds; avoids hanging a request on a dead SMTP server
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER)


# --------------------------------------------------------------------------
# Media files (profile pictures and cover photos)
# --------------------------------------------------------------------------
# Local development: files are written to MEDIA_ROOT and served by Django
# (see config/urls.py, DEBUG only). Production: serve MEDIA_ROOT from the web
# server, or point the default storage at object storage (S3, GCS, ...) with
# MEDIA_STORAGE_BACKEND. Nothing here is hard-coded to a domain.
MEDIA_URL = os.environ.get("MEDIA_URL", "media/")
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", "media"))
if not MEDIA_ROOT.is_absolute():
    MEDIA_ROOT = BASE_DIR / MEDIA_ROOT

# The STORAGES setting (public + private message attachments) is defined further below.

# --------------------------------------------------------------------------
# Profiles module settings
# --------------------------------------------------------------------------
PROFILE_PICTURE_MAX_BYTES = env_int("PROFILE_PICTURE_MAX_BYTES", 2 * 1024 * 1024)  # 2 MB
PROFILE_COVER_MAX_BYTES = env_int("PROFILE_COVER_MAX_BYTES", 5 * 1024 * 1024)  # 5 MB
PROFILE_IMAGE_MAX_PIXELS = env_int("PROFILE_IMAGE_MAX_PIXELS", 25_000_000)
PROFILE_THROTTLE_RATES = {"profile_upload": os.environ.get("PROFILE_UPLOAD_RATE", "30/hour")}


# --------------------------------------------------------------------------
# Friends module settings
# --------------------------------------------------------------------------
# Per-user rate limits for friend write actions (reads and DELETE are not throttled).
FRIENDS_THROTTLE_RATES = {
    "friends_request": os.environ.get("FRIENDS_REQUEST_RATE", "30/hour"),
    "friends_action": os.environ.get("FRIENDS_ACTION_RATE", "300/hour"),
}
# After a request is REJECTED the sender may not ask the same person again for this many
# hours (anti-harassment). 0 disables the cool-down.
FRIENDS_REJECTION_COOLDOWN_HOURS = env_int("FRIENDS_REJECTION_COOLDOWN_HOURS", 24)
# Whether the status API tells a user that somebody blocked them ("blocked_you").
# Set to False to report such a user as "not_friends" instead.
FRIENDS_REVEAL_BLOCKED_BY_OTHER = env_bool("FRIENDS_REVEAL_BLOCKED_BY_OTHER", True)
# TEMPORARY GET /api/friends/discover/ until the shared Search module exists.
FRIENDS_ENABLE_TEMP_DISCOVERY = env_bool("FRIENDS_ENABLE_TEMP_DISCOVERY", True)


# --------------------------------------------------------------------------
# Social module settings
# --------------------------------------------------------------------------
SOCIAL_IMAGE_MAX_BYTES = env_int("SOCIAL_IMAGE_MAX_BYTES", 5 * 1024 * 1024)  # 5 MB per image
SOCIAL_MAX_IMAGES_PER_POST = env_int("SOCIAL_MAX_IMAGES_PER_POST", 6)
SOCIAL_THROTTLE_RATES = {
    "social_post": os.environ.get("SOCIAL_POST_RATE", "30/hour"),
    "social_comment": os.environ.get("SOCIAL_COMMENT_RATE", "90/hour"),
    "social_interaction": os.environ.get("SOCIAL_INTERACTION_RATE", "600/hour"),
    "social_report": os.environ.get("SOCIAL_REPORT_RATE", "20/hour"),
}


# --------------------------------------------------------------------------
# Messaging module settings (see messaging/README.md)
# --------------------------------------------------------------------------
# Users who are NOT friends may exchange at most this many messages IN TOTAL (both senders
# together) in their direct conversation. 0 = non-friends cannot message at all.
MESSAGING_NON_FRIEND_MESSAGE_LIMIT = env_int("MESSAGING_NON_FRIEND_MESSAGE_LIMIT", 4)
MESSAGING_MAX_MESSAGE_LENGTH = env_int("MESSAGING_MAX_MESSAGE_LENGTH", 5000)
# Minutes after sending during which a message may be edited / deleted for everyone (0 = no limit).
MESSAGING_EDIT_WINDOW_MINUTES = env_int("MESSAGING_EDIT_WINDOW_MINUTES", 15)
MESSAGING_DELETE_FOR_EVERYONE_WINDOW_MINUTES = env_int(
    "MESSAGING_DELETE_FOR_EVERYONE_WINDOW_MINUTES", 60
)
# A new incoming message moves an archived conversation back to the recipient's inbox.
MESSAGING_UNARCHIVE_ON_NEW_MESSAGE = env_bool("MESSAGING_UNARCHIVE_ON_NEW_MESSAGE", True)
# Attachments
MESSAGING_MAX_ATTACHMENTS_PER_MESSAGE = env_int("MESSAGING_MAX_ATTACHMENTS_PER_MESSAGE", 5)
MESSAGING_IMAGE_MAX_BYTES = env_int("MESSAGING_IMAGE_MAX_BYTES", 5 * 1024 * 1024)  # 5 MB
MESSAGING_FILE_MAX_BYTES = env_int("MESSAGING_FILE_MAX_BYTES", 10 * 1024 * 1024)  # 10 MB
# Lifetime of the signed download links returned for private attachments.
MESSAGING_ATTACHMENT_URL_MAX_AGE_SECONDS = env_int("MESSAGING_ATTACHMENT_URL_MAX_AGE_SECONDS", 600)
# Private attachments are stored OUTSIDE MEDIA_ROOT, so DEBUG media serving never exposes them.
PRIVATE_MEDIA_ROOT = Path(os.environ.get("PRIVATE_MEDIA_ROOT", "private_media"))
if not PRIVATE_MEDIA_ROOT.is_absolute():
    PRIVATE_MEDIA_ROOT = BASE_DIR / PRIVATE_MEDIA_ROOT
# Presence: "friends" (default) | "participants" | "nobody". Blocks always hide presence.
MESSAGING_PRESENCE_VISIBILITY = os.environ.get("MESSAGING_PRESENCE_VISIBILITY", "friends")
MESSAGING_PRESENCE_TTL_SECONDS = env_int("MESSAGING_PRESENCE_TTL_SECONDS", 70)
MESSAGING_TYPING_TTL_SECONDS = env_int("MESSAGING_TYPING_TTL_SECONDS", 6)
# Per-user rate limits shared by REST and WebSocket ("<count>/<sec|min|hour|day>").
MESSAGING_THROTTLE_RATES = {
    "messaging_send": os.environ.get("MESSAGING_SEND_RATE", "60/min"),
    "messaging_action": os.environ.get("MESSAGING_ACTION_RATE", "300/min"),
    "messaging_upload": os.environ.get("MESSAGING_UPLOAD_RATE", "60/hour"),
    "messaging_ws_event": os.environ.get("MESSAGING_WS_EVENT_RATE", "120/min"),
}
# Browser origins allowed to open WebSockets (defaults to the CORS origins).
MESSAGING_WS_ALLOWED_ORIGINS = env_list(
    "MESSAGING_WS_ALLOWED_ORIGINS", ",".join(env_list("CORS_ALLOWED_ORIGINS", ""))
)


# --------------------------------------------------------------------------
# Common module (shared file validation)
# --------------------------------------------------------------------------
COMMON_MAX_IMAGE_BYTES = env_int("COMMON_MAX_IMAGE_BYTES", 5 * 1024 * 1024)  # 5 MB
COMMON_MAX_PDF_BYTES = env_int("COMMON_MAX_PDF_BYTES", 10 * 1024 * 1024)  # 10 MB


# --------------------------------------------------------------------------
# Announcements module
# --------------------------------------------------------------------------
ANNOUNCEMENT_COVER_MAX_BYTES = env_int("ANNOUNCEMENT_COVER_MAX_BYTES", 5 * 1024 * 1024)
# Hours before the start time at which bookmarkers get "announcement.reminder"
# (sent by: python manage.py send_announcement_reminders, run it from cron every 15-60 min).
ANNOUNCEMENT_REMINDER_HOURS = env_int("ANNOUNCEMENT_REMINDER_HOURS", 24)
# Who is notified when an announcement is published: "friends" (author's friends) or "none".
ANNOUNCEMENT_PUBLISH_AUDIENCE = os.environ.get("ANNOUNCEMENT_PUBLISH_AUDIENCE", "friends")
ANNOUNCEMENTS_THROTTLE_RATES = {
    "announcement_write": os.environ.get("ANNOUNCEMENT_WRITE_RATE", "60/hour"),
    "announcement_interaction": os.environ.get("ANNOUNCEMENT_INTERACTION_RATE", "600/hour"),
    "announcement_report": os.environ.get("ANNOUNCEMENT_REPORT_RATE", "20/hour"),
    "announcement_search": os.environ.get("ANNOUNCEMENT_SEARCH_RATE", "300/hour"),
}


# --------------------------------------------------------------------------
# Achievements module
# --------------------------------------------------------------------------
ACHIEVEMENT_EVIDENCE_IMAGE_MAX_BYTES = env_int("ACHIEVEMENT_EVIDENCE_IMAGE_MAX_BYTES", 5 * 1024 * 1024)
ACHIEVEMENT_EVIDENCE_PDF_MAX_BYTES = env_int("ACHIEVEMENT_EVIDENCE_PDF_MAX_BYTES", 10 * 1024 * 1024)
ACHIEVEMENT_MAX_EVIDENCE_FILES = env_int("ACHIEVEMENT_MAX_EVIDENCE_FILES", 10)
ACHIEVEMENT_MAX_FEATURED = env_int("ACHIEVEMENT_MAX_FEATURED", 5)  # per user
ACHIEVEMENT_EVIDENCE_URL_MAX_AGE_SECONDS = env_int("ACHIEVEMENT_EVIDENCE_URL_MAX_AGE_SECONDS", 600)
ACHIEVEMENTS_THROTTLE_RATES = {
    "achievement_write": os.environ.get("ACHIEVEMENT_WRITE_RATE", "60/hour"),
    "achievement_upload": os.environ.get("ACHIEVEMENT_UPLOAD_RATE", "60/hour"),
    "achievement_review": os.environ.get("ACHIEVEMENT_REVIEW_RATE", "600/hour"),
}


# --------------------------------------------------------------------------
# Notifications module
# --------------------------------------------------------------------------
# E-mail copies of important notifications (see notifications/README.md for which types).
NOTIFICATIONS_EMAIL_ENABLED = env_bool("NOTIFICATIONS_EMAIL_ENABLED", bool(os.environ.get("EMAIL_HOST")))
# Base URL of the React app, used to build links inside notification e-mails.
FRONTEND_BASE_URL = os.environ.get("FRONTEND_BASE_URL", "http://localhost:5173").rstrip("/")
# Read notifications older than this are removed by `python manage.py cleanup_notifications`.
NOTIFICATIONS_RETENTION_DAYS = env_int("NOTIFICATIONS_RETENTION_DAYS", 90)
NOTIFICATIONS_THROTTLE_RATES = {
    "notification_action": os.environ.get("NOTIFICATION_ACTION_RATE", "600/hour"),
}


# --------------------------------------------------------------------------
# Storage
# --------------------------------------------------------------------------
# "default" = public media (profile pictures, post images).
# "messaging_private" = message attachments; never served by URL, only through the
# authenticated download endpoint. Point it at private object storage in production with
# MESSAGING_PRIVATE_STORAGE_BACKEND (e.g. storages.backends.s3.S3Storage + a private bucket).
STORAGES = {
    "default": {
        "BACKEND": os.environ.get(
            "MEDIA_STORAGE_BACKEND", "django.core.files.storage.FileSystemStorage"
        )
    },
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    "messaging_private": (
        {"BACKEND": os.environ["MESSAGING_PRIVATE_STORAGE_BACKEND"]}
        if os.environ.get("MESSAGING_PRIVATE_STORAGE_BACKEND")
        else {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
            "OPTIONS": {"location": str(PRIVATE_MEDIA_ROOT), "base_url": None},
        }
    ),
    # Other private files (achievement evidence). Same folder as messaging, different prefix
    # ("achievements/..."); never served by URL, only through authenticated endpoints.
    "private": (
        {"BACKEND": os.environ["PRIVATE_STORAGE_BACKEND"]}
        if os.environ.get("PRIVATE_STORAGE_BACKEND")
        else {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
            "OPTIONS": {"location": str(PRIVATE_MEDIA_ROOT), "base_url": None},
        }
    ),
}


# --------------------------------------------------------------------------
# Cache (used by throttling)
# --------------------------------------------------------------------------
# With several server processes, throttle counters must live in a shared
# cache. Set REDIS_URL in production (requires `pip install redis`).
if os.environ.get("REDIS_URL"):
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": os.environ["REDIS_URL"],
        }
    }
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


# --------------------------------------------------------------------------
# Django Channels (WebSockets for Messaging)
# --------------------------------------------------------------------------
# Production MUST use Redis: the in-memory layer only works inside ONE process, so with several
# workers a message sent through one worker would never reach sockets held by another.
if os.environ.get("REDIS_URL"):
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [os.environ["REDIS_URL"]], "capacity": 1500, "expiry": 60},
        }
    }
else:
    if not DEBUG and not env_bool("MESSAGING_ALLOW_INMEMORY_CHANNEL_LAYER", False):
        raise ImproperlyConfigured(
            "REDIS_URL is required in production for the Messaging WebSocket channel layer."
        )
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}


# --------------------------------------------------------------------------
# CORS (React + Vite frontend)
# --------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173" if DEBUG else "",
)
# Tokens travel in the Authorization header, not in cookies.
CORS_ALLOW_CREDENTIALS = False
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", "")


# --------------------------------------------------------------------------
# Internationalisation / static files
# --------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"


# --------------------------------------------------------------------------
# Production security
# --------------------------------------------------------------------------
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"

if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = env_int("DJANGO_HSTS_SECONDS", 31536000)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    if env_bool("DJANGO_BEHIND_PROXY", False):
        # Only enable when your proxy sets X-Forwarded-Proto and strips it
        # from incoming client requests.
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


# --------------------------------------------------------------------------
# Logging (OTP values, passwords and tokens are never logged anywhere)
# --------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "[{asctime}] {levelname} {name}: {message}", "style": "{"},
    },
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "simple"}},
    "loggers": {
        "accounts": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "profiles": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "friends": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "social": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "messaging": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "common": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "announcements": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "achievements": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "notifications": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
