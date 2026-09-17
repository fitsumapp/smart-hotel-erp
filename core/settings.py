"""
Django settings for Smart Hotel ERP — Single-Tenant Edition
Using standard PostgreSQL with Django ORM.
"""

from pathlib import Path
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

ENVIRONMENT = os.getenv("DJANGO_ENV", "development").lower()
IS_PRODUCTION = ENVIRONMENT == "production"


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


def require_env(name):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} must be configured when DJANGO_ENV=production.")
    return value


SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-dev-only-key")
DEBUG = env_bool("DEBUG", not IS_PRODUCTION)
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1,.localhost")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", "")

if IS_PRODUCTION:
    SECRET_KEY = require_env("SECRET_KEY")
    if SECRET_KEY.startswith("django-insecure") or SECRET_KEY == "django-insecure-dev-only-key":
        raise RuntimeError("SECRET_KEY must be a strong production secret.")
    if DEBUG:
        raise RuntimeError("DEBUG must be False when DJANGO_ENV=production.")
    if not ALLOWED_HOSTS:
        raise RuntimeError("ALLOWED_HOSTS must be configured when DJANGO_ENV=production.")
    if "*" in ALLOWED_HOSTS:
        raise RuntimeError("Wildcard ALLOWED_HOSTS is not allowed in production.")
    if not CSRF_TRUSTED_ORIGINS:
        raise RuntimeError("CSRF_TRUSTED_ORIGINS must be configured when DJANGO_ENV=production.")
    if any("*" in origin for origin in CSRF_TRUSTED_ORIGINS):
        raise RuntimeError("Wildcard CSRF_TRUSTED_ORIGINS is not allowed in production.")



# ── Installed Apps ────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    "unfold",  # Must be before django.contrib.admin
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "users",
    "hotel",
]

# ── Middleware ─────────────────────────────────────────────────────────────────
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",                 # ← FIRST (CORS)
    "django.middleware.security.SecurityMiddleware",
    "core.security.SecurityHeadersMiddleware",
    "core.observability.ObservabilityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.middleware.cache.UpdateCacheMiddleware",         # ← Needed for no-cache
    "django.middleware.cache.FetchFromCacheMiddleware",      # ← Needed for no-cache
]

# Disable all server-side caching — API responses must always be fresh
CACHE_MIDDLEWARE_SECONDS = 0
CACHE_MIDDLEWARE_KEY_PREFIX = ""
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    }
}

# ── URL Configuration ──────────────────────────────────────────────────────────
ROOT_URLCONF = "core.urls"

# ── Database — Neon.tech PostgreSQL (SSL required) ────────────────────────────
# Neon.tech connection string support (takes priority if set)
_neon_url = os.getenv("DATABASE_URL", "")

if _neon_url:
    import dj_database_url
    _db_config = dj_database_url.parse(_neon_url)
    _db_config["ENGINE"] = "django.db.backends.postgresql"
    _db_config.setdefault("OPTIONS", {})["sslmode"] = "require"
    _db_config["CONN_MAX_AGE"] = int(os.getenv("DB_CONN_MAX_AGE", "60"))
    _db_config["CONN_HEALTH_CHECKS"] = True
    # Neon PgBouncer pooler (-pooler) rejects startup parameters like statement_timeout.
    _is_pooler = "-pooler" in _neon_url or os.getenv("DB_IS_POOLER", "").lower() in ("true", "1")
    if not _is_pooler and os.getenv("DB_ENABLE_TIMEOUT_OPTIONS", "false").lower() == "true":
        _db_config["OPTIONS"]["options"] = f"-c statement_timeout={int(os.getenv('DB_STATEMENT_TIMEOUT_MS', '30000'))} -c lock_timeout={int(os.getenv('DB_LOCK_TIMEOUT_MS', '5000'))} -c idle_in_transaction_session_timeout={int(os.getenv('DB_IDLE_TX_TIMEOUT_MS', '60000'))}"
    DATABASES = {"default": _db_config}
else:
    if IS_PRODUCTION:
        for _required_db_env in ("DB_NAME", "DB_USER", "DB_PASSWORD", "DB_HOST"):
            require_env(_required_db_env)
    _db_options = {"sslmode": os.getenv("DB_SSLMODE", "prefer")}
    _is_pooler = "-pooler" in os.getenv("DB_HOST", "") or os.getenv("DB_IS_POOLER", "").lower() in ("true", "1")
    if not _is_pooler and os.getenv("DB_ENABLE_TIMEOUT_OPTIONS", "false").lower() == "true":
        _db_options["options"] = f"-c statement_timeout={int(os.getenv('DB_STATEMENT_TIMEOUT_MS', '30000'))} -c lock_timeout={int(os.getenv('DB_LOCK_TIMEOUT_MS', '5000'))} -c idle_in_transaction_session_timeout={int(os.getenv('DB_IDLE_TX_TIMEOUT_MS', '60000'))}"
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("DB_NAME", "hotel_erp_db"),
            "USER": os.getenv("DB_USER", "postgres"),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": os.getenv("DB_HOST", "localhost"),
            "PORT": os.getenv("DB_PORT", "5432"),
            "CONN_MAX_AGE": int(os.getenv("DB_CONN_MAX_AGE", "60")),
            "CONN_HEALTH_CHECKS": True,
            "OPTIONS": _db_options,
        }
    }

# ── Templates ─────────────────────────────────────────────────────────────────
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

WSGI_APPLICATION = "core.wsgi.application"

UNFOLD = {
    "SITE_TITLE": "Smart Hotel ERP",
    "SITE_HEADER": "Hotel Management System",
    "SITE_URL": "/",
    # Logo via external URL (no local static file required)
    "SITE_LOGO": {
        "light": lambda request: "https://dummyimage.com/150x50/1e3a8a/ffffff.png&text=SMART+ERP",
        "dark": lambda request: "https://dummyimage.com/150x50/0f172a/ffffff.png&text=SMART+ERP",
    },
    "COLORS": {
        "primary": {
            "50": "#eff6ff",
            "100": "#dbeafe",
            "200": "#bfdbfe",
            "300": "#93c5fd",
            "400": "#60a5fa",
            "500": "#3b82f6",
            "600": "#2563eb",
            "700": "#1d4ed8",
            "800": "#1e40af",  # Midnight Blue
            "900": "#1e3a8a",
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": True,
    },
}

# ── Auth ──────────────────────────────────────────────────────────────────────
AUTH_USER_MODEL = "users.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ── Internationalization ───────────────────────────────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Addis_Ababa"
USE_I18N = True
USE_TZ = True

# ── Static & Media ────────────────────────────────────────────────────────────
STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
STATICFILES_DIRS = []
MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── Email ─────────────────────────────────────────────────────────────────────
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv("EMAIL_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_PASS")
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

# ── Payment (Chapa) ───────────────────────────────────────────────────────────
CHAPA_SECRET_KEY = os.getenv("CHAPA_SECRET_KEY", "")
CHAPA_WEBHOOK_SECRET = os.getenv("CHAPA_WEBHOOK_SECRET", "")
CHAPA_BASE_URL = os.getenv("CHAPA_BASE_URL", "https://api.chapa.co/v1")
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:3000")
BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "http://127.0.0.1:8000")

if IS_PRODUCTION:
    CHAPA_SECRET_KEY = require_env("CHAPA_SECRET_KEY")
    CHAPA_WEBHOOK_SECRET = require_env("CHAPA_WEBHOOK_SECRET")
    require_env("FRONTEND_BASE_URL")
    require_env("BACKEND_BASE_URL")

# ── CORS Settings ──────────────────────────────────────────────────────────────
CORS_ALLOW_ALL_ORIGINS = env_bool("CORS_ALLOW_ALL_ORIGINS", False)
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:8000" if not IS_PRODUCTION else "")
if CORS_ALLOW_ALL_ORIGINS and CORS_ALLOW_CREDENTIALS:
    raise RuntimeError("Do not combine wildcard CORS origins with credential support.")
if IS_PRODUCTION and CORS_ALLOW_ALL_ORIGINS:
    raise RuntimeError("CORS_ALLOW_ALL_ORIGINS must be False in production.")
if IS_PRODUCTION and not CORS_ALLOWED_ORIGINS:
    raise RuntimeError("CORS_ALLOWED_ORIGINS must be configured in production.")
from corsheaders.defaults import default_headers
CORS_ALLOW_HEADERS = list(default_headers) + [
    "x-tenant-schema",
]

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", IS_PRODUCTION)
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", IS_PRODUCTION)
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", IS_PRODUCTION)
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000" if IS_PRODUCTION else "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", IS_PRODUCTION)
SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", IS_PRODUCTION)
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv("DATA_UPLOAD_MAX_MEMORY_SIZE", str(5 * 1024 * 1024)))
FILE_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv("FILE_UPLOAD_MAX_MEMORY_SIZE", str(5 * 1024 * 1024)))

RELEASE_VERSION = os.getenv("RELEASE_VERSION", os.getenv("GIT_COMMIT", "development"))[:80]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {"()": "core.observability.JsonFormatter"},
        "verbose": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "json" if IS_PRODUCTION else "verbose"}},
    "root": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL", "INFO")},
}

# ── REST Framework ────────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "users.authentication.VersionedJWTAuthentication",
    ),
    "EXCEPTION_HANDLER": "core.api.api_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "rest_framework.schemas.openapi.AutoSchema",
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "core.api.V1PageNumberPagination",
    "DEFAULT_FILTER_BACKENDS": [
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/day",
        "user": "1000/day",
        "login": "10/minute",
        "register": "5/hour",
        "otp": "5/hour",
        "mfa": "10/hour",
    },
}

# ── JWT ───────────────────────────────────────────────────────────────────────
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
}
