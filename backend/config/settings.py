import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-change-me")
DEBUG = os.environ.get("DEBUG", "true").lower() in ("1", "true", "yes")

ALLOWED_HOSTS = [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "*").split(",") if h.strip()]
if DEBUG:
    ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "apps.users",
    "apps.authentication",
    "apps.products",
    "apps.rbac",
    "apps.stocks",
    "apps.stock_finance",
    "apps.categories",
    "apps.posts",
    "apps.media_upload",
    "apps.settings_app",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "common.request_logging_middleware.RequestLoggingMiddleware",
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
        "DIRS": [],
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

# Database — existing PostgreSQL (Flyway-managed schema)
_db_url = os.environ.get("DATABASE_URL", "postgresql://mvp:mvp@localhost:5432/mvpdb")
if _db_url.startswith("postgresql://"):
    from urllib.parse import urlparse

    u = urlparse(_db_url)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": u.path.lstrip("/") or "mvpdb",
            "USER": u.username or "mvp",
            "PASSWORD": u.password or "",
            "HOST": u.hostname or "localhost",
            "PORT": str(u.port or 5432),
            "OPTIONS": {"options": "-c timezone=UTC"},
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": str(BASE_DIR / "db.sqlite3"),
        }
    }

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
STATIC_URL = "/static/"

# Match Spring Boot URLs without trailing slash redirects
APPEND_SLASH = False

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "common.jwt_auth.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
    "EXCEPTION_HANDLER": "common.exceptions.custom_exception_handler",
}

# JWT / app
APP_JWT_SECRET = os.environ.get(
    "APP_JWT_SECRET",
    "0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF",
)
APP_JWT_ACCESS_TOKEN_MINUTES = int(os.environ.get("APP_JWT_ACCESS_TOKEN_MINUTES", "15"))
APP_JWT_REFRESH_TOKEN_DAYS = int(os.environ.get("APP_JWT_REFRESH_TOKEN_DAYS", "7"))
APP_AUTH_PASSWORD_RESET_MINUTES = int(os.environ.get("APP_AUTH_PASSWORD_RESET_MINUTES", "30"))
APP_AUTH_PASSWORD_RESET_EXPOSE_TOKEN = os.environ.get("APP_AUTH_PASSWORD_RESET_EXPOSE_TOKEN", "true").lower() in (
    "1",
    "true",
    "yes",
)
APP_GOOGLE_CLIENT_ID = os.environ.get("APP_GOOGLE_CLIENT_ID", "")
APP_SEED_ADMIN_EMAIL = os.environ.get("APP_SEED_ADMIN_EMAIL", "admin@example.com")
APP_SEED_ADMIN_PASSWORD = os.environ.get("APP_SEED_ADMIN_PASSWORD", "Admin@123")

APP_MEDIA_PUBLIC_BASE_URL = os.environ.get("APP_MEDIA_PUBLIC_BASE_URL", "http://localhost:8080")

# CORS
_web = os.environ.get("APP_CORS_WEB_ORIGIN", "http://localhost:3000")
# Vite default dev port is 5173 (compose / docs use this; override via APP_CORS_ADMIN_ORIGIN if needed)
_admin = os.environ.get("APP_CORS_ADMIN_ORIGIN", "http://localhost:5173")
_cors_extra = [
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:5173",
]
CORS_ALLOWED_ORIGINS = list(dict.fromkeys([_web, _admin, *_cors_extra]))
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https?://localhost(:\d+)?$",
    r"^https?://127\.0\.0\.1(:\d+)?$",
    r"^https?://192\.168\.\d{1,3}\.\d{1,3}(:\d+)?$",
    r"^https?://10\.\d{1,3}\.\d{1,3}\.\d{1,3}(:\d+)?$",
    r"^https?://172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}(:\d+)?$",
]
CORS_ALLOW_CREDENTIALS = True
CORS_EXPOSE_HEADERS = ["Authorization"]
CORS_ALLOW_HEADERS = ["*"]

# Stock finance chart
APP_STOCK_FINANCE_CHART_BATCH_SIZE = int(os.environ.get("APP_STOCK_FINANCE_CHART_BATCH_SIZE", "60"))
APP_STOCK_FINANCE_CHART_MIN_AVG_VOLUME_20 = int(os.environ.get("APP_STOCK_FINANCE_CHART_MIN_AVG_VOLUME_20", "100000"))
APP_STOCK_FINANCE_CHART_MIN_DELAY_MS = int(os.environ.get("APP_STOCK_FINANCE_CHART_MIN_DELAY_MS", "2000"))
APP_STOCK_FINANCE_CHART_MAX_DELAY_MS = int(os.environ.get("APP_STOCK_FINANCE_CHART_MAX_DELAY_MS", "6000"))
APP_STOCK_FINANCE_CHART_MAX_RETRIES = int(os.environ.get("APP_STOCK_FINANCE_CHART_MAX_RETRIES", "2"))
APP_STOCK_FINANCE_CHART_MAX_CONSECUTIVE_FAILURES = int(
    os.environ.get("APP_STOCK_FINANCE_CHART_MAX_CONSECUTIVE_FAILURES", "5")
)

# Console access-style logs for every request (CLI). Set APP_LOG_REQUESTS=0 to disable.
_LOG_REQUESTS = os.environ.get("APP_LOG_REQUESTS", "1").lower() in ("1", "true", "yes")
# Used by RequestLoggingMiddleware (avoid circular import of _LOG_REQUESTS)
APP_LOG_REQUESTS = _LOG_REQUESTS

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "api_request": {
            "format": "[API] %(message)s",
        },
    },
    "handlers": {
        "console_api": {
            "class": "logging.StreamHandler",
            "formatter": "api_request",
        },
    },
    "loggers": {
        "api.request": {
            "handlers": ["console_api"],
            "level": "INFO" if _LOG_REQUESTS else "WARNING",
            "propagate": False,
        },
    },
}
