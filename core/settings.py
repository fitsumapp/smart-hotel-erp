"""
Django settings for Smart Hotel ERP — Multi-Tenant SaaS Edition
Using django-tenants with PostgreSQL schema isolation.
"""

from pathlib import Path
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-change-me-in-production")
DEBUG = os.getenv("DEBUG", "True") == "True"
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1,.localhost,.acrmatech.com,.ngrok-free.app").split(",")
CSRF_TRUSTED_ORIGINS = os.getenv("CSRF_TRUSTED_ORIGINS", "https://*.acrmatech.com,https://*.ngrok-free.app").split(",")



# ── Multi-Tenant App Split ────────────────────────────────────────────────────
# SHARED_APPS  → tables live in the PUBLIC schema (platform-level)
# TENANT_APPS  → tables live in each hotel's OWN schema (isolated)

SHARED_APPS = [
    # django-tenants MUST be first
    "django_tenants",
    # Public-schema models: Hotel, Domain, Package
    "tenants",
    # Shared Django internals + User model
    "unfold",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Shared third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    # users app lives in SHARED so AUTH_USER_MODEL resolves in public schema
    "users",
]

TENANT_APPS = [
    # Hotel-specific data — each hotel gets its own schema copy
    "hotel",
]

# Django requires INSTALLED_APPS = union of both lists (shared first, then unique tenants)
INSTALLED_APPS = list(SHARED_APPS) + [app for app in TENANT_APPS if app not in SHARED_APPS]

# Tenant model pointers
TENANT_MODEL = "tenants.Hotel"
TENANT_DOMAIN_MODEL = "tenants.Domain"

# ── Middleware ─────────────────────────────────────────────────────────────────
# TenantMainMiddleware MUST be first — it sets the DB schema for each request
MIDDLEWARE = [
    # CorsMiddleware MUST be first — it must wrap every response (including
    # preflight OPTIONS replies) with Access-Control-Allow-* headers BEFORE
    # any other middleware can short-circuit the request.
    "corsheaders.middleware.CorsMiddleware",                 # ← FIRST (CORS)
    "django_tenants.middleware.main.TenantMainMiddleware",   # ← tenant routing
    "tenants.middleware.LocalhostTenantRoutingMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Cross-tenant isolation — hotel staff cannot access other hotels
    "tenants.middleware.TenantUserIsolationMiddleware",      # ← LAST
]

# ── URL Configuration ──────────────────────────────────────────────────────────
# ROOT_URLCONF        → served for every HOTEL subdomain  (e.g. atlas.myerp.com)
# PUBLIC_SCHEMA_URLCONF → served for the PUBLIC domain     (e.g. myerp.com)
ROOT_URLCONF = "core.urls"
PUBLIC_SCHEMA_URLCONF = "core.public_urls"

# ── Database — Neon.tech PostgreSQL (SSL required) ────────────────────────────
DATABASE_ROUTERS = ["django_tenants.routers.TenantSyncRouter"]

# Neon.tech connection string support (takes priority if set)
_neon_url = os.getenv("DATABASE_URL", "")

if _neon_url:
    import dj_database_url
    _db_config = dj_database_url.parse(_neon_url)
    _db_config["ENGINE"] = "django_tenants.postgresql_backend"
    _db_config.setdefault("OPTIONS", {})["sslmode"] = "require"
    DATABASES = {"default": _db_config}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django_tenants.postgresql_backend",
            "NAME": os.getenv("DB_NAME", "hotel_erp_db"),
            "USER": os.getenv("DB_USER", "postgres"),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": os.getenv("DB_HOST", "localhost"),
            "PORT": os.getenv("DB_PORT", "5432"),
            "OPTIONS": {
                "sslmode": os.getenv("DB_SSLMODE", "prefer"),
            },
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
        "show_all_applications": False,
        "navigation": [
            {
                "title": "Platform Administration",
                "separator": True,
                "items": [
                    {
                        "title": "Registered Hotels",
                        "icon": "domain",
                        "link": "/admin/tenants/hotel/",
                    },
                    {
                        "title": "Subdomains",
                        "icon": "link",
                        "link": "/admin/tenants/domain/",
                    },
                    {
                        "title": "Subscription Packages",
                        "icon": "inventory_2",
                        "link": "/admin/tenants/package/",
                    },
                ],
            },
            {
                "title": "Access Management",
                "separator": True,
                "items": [
                    {
                        "title": "Platform Admins",
                        "icon": "shield",
                        "link": "/admin/users/user/",
                    },
                ],
            },
        ],
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

# ── CORS Settings ──────────────────────────────────────────────────────────────
CORS_ALLOW_ALL_ORIGINS = True  # For development, allow all. In production, we can be more specific.
CORS_ALLOW_CREDENTIALS = True
from corsheaders.defaults import default_headers
CORS_ALLOW_HEADERS = list(default_headers) + [
    "x-tenant-schema",
]

# ── REST Framework ────────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

# ── JWT ───────────────────────────────────────────────────────────────────────
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(days=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": False,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
}
