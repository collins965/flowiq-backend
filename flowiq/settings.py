from pathlib import Path
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent

# ─────────────────────────────────────────────────────────────────────────────
# Core
# ─────────────────────────────────────────────────────────────────────────────

SECRET_KEY = config("DJANGO_SECRET_KEY")
DEBUG = config("DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1").split(",")

# ─────────────────────────────────────────────────────────────────────────────
# Apps
# ─────────────────────────────────────────────────────────────────────────────

INSTALLED_APPS = [
    # Django built-ins
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.staticfiles",

    # Third party
    "rest_framework",
    "corsheaders",

    # FlowIQ apps
    "core",
    "accounts",
    "transactions",
    "budgets",
    "savings",
    "debts",
    "investments",
    "tax",
    "fraud",
    "reports",
    "ai_chat",
    "notifications",
    "location",
    "payments",
]

# ─────────────────────────────────────────────────────────────────────────────
# Middleware
# ─────────────────────────────────────────────────────────────────────────────

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",         # must be first
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",     # CSRF protection
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# ─────────────────────────────────────────────────────────────────────────────
# URLs & WSGI
# ─────────────────────────────────────────────────────────────────────────────

ROOT_URLCONF = "flowiq.urls"
WSGI_APPLICATION = "flowiq.wsgi.application"

# ─────────────────────────────────────────────────────────────────────────────
# Templates (needed for DRF browsable API and error pages)
# ─────────────────────────────────────────────────────────────────────────────

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
            ],
        },
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# Database
# ─────────────────────────────────────────────────────────────────────────────

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("DB_NAME", default="flowiq"),
        "USER": config("DB_USER", default="postgres"),
        "PASSWORD": config("DB_PASSWORD", default=""),
        "HOST": config("DB_HOST", default="localhost"),
        "PORT": config("DB_PORT", default="5432"),
        "OPTIONS": {
            "connect_timeout": 10,
        },
        "CONN_MAX_AGE": 60,  # reuse DB connections for 60s (better performance)
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# Authentication
# ─────────────────────────────────────────────────────────────────────────────

AUTH_USER_MODEL = "core.User"


# ─────────────────────────────────────────────────────────────────────────────
# Django REST Framework
# ─────────────────────────────────────────────────────────────────────────────

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "core.authentication.SupabaseJWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        # Remove BrowsableAPIRenderer in production for security
        # Add it back in development only:
        # "rest_framework.renderers.BrowsableAPIRenderer",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "EXCEPTION_HANDLER": "core.exceptions.custom_exception_handler",  # consistent error format
}

# ─────────────────────────────────────────────────────────────────────────────
# CORS
# ─────────────────────────────────────────────────────────────────────────────

CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="http://localhost:5173,http://127.0.0.1:5173",
).split(",")
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]

# ─────────────────────────────────────────────────────────────────────────────
# File uploads (for bank statement imports, profile photos, receipts)
# ─────────────────────────────────────────────────────────────────────────────

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Max upload size: 50MB (bank statements can be large)
DATA_UPLOAD_MAX_MEMORY_SIZE = 52_428_800   # 50MB in bytes
FILE_UPLOAD_MAX_MEMORY_SIZE = 52_428_800

# ─────────────────────────────────────────────────────────────────────────────
# Static files
# ─────────────────────────────────────────────────────────────────────────────

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# ─────────────────────────────────────────────────────────────────────────────
# Internationalisation
# ─────────────────────────────────────────────────────────────────────────────

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Nairobi"
USE_I18N = True
USE_TZ = True

# ─────────────────────────────────────────────────────────────────────────────
# Primary key type
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ─────────────────────────────────────────────────────────────────────────────
# Email
# ─────────────────────────────────────────────────────────────────────────────

EMAIL_BACKEND = config(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
    # ↑ prints emails to terminal in development
    # In production set to: "django.core.mail.backends.smtp.EmailBackend"
)
EMAIL_HOST = config("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = True
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="FlowIQ <hello@flowiq.app>")

# ─────────────────────────────────────────────────────────────────────────────
# External services
# ─────────────────────────────────────────────────────────────────────────────

# Supabase — used for JWT verification
SUPABASE_JWT_SECRET = config("SUPABASE_JWT_SECRET", default="")
SUPABASE_URL = config("SUPABASE_URL", default="")

# Anthropic — FlowAI
ANTHROPIC_API_KEY = config("ANTHROPIC_API_KEY", default="")

# Flutterwave — payments
FLUTTERWAVE_SECRET_KEY = config("FLUTTERWAVE_SECRET_KEY", default="")
FLUTTERWAVE_PUBLIC_KEY = config("FLUTTERWAVE_PUBLIC_KEY", default="")
FLUTTERWAVE_WEBHOOK_SECRET = config("FLUTTERWAVE_WEBHOOK_SECRET", default="")

# M-Pesa (Daraja API)
MPESA_CONSUMER_KEY = config("MPESA_CONSUMER_KEY", default="")
MPESA_CONSUMER_SECRET = config("MPESA_CONSUMER_SECRET", default="")
MPESA_SHORTCODE = config("MPESA_SHORTCODE", default="")
MPESA_PASSKEY = config("MPESA_PASSKEY", default="")
MPESA_CALLBACK_URL = config("MPESA_CALLBACK_URL", default="")
MPESA_ENVIRONMENT = config("MPESA_ENVIRONMENT", default="sandbox")  # sandbox | production

# Africa's Talking — SMS 2FA
AFRICASTALKING_USERNAME = config("AFRICASTALKING_USERNAME", default="")
AFRICASTALKING_API_KEY = config("AFRICASTALKING_API_KEY", default="")

# ─────────────────────────────────────────────────────────────────────────────
# Security headers (important even in development)
# ─────────────────────────────────────────────────────────────────────────────

SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True

# These should be True in production (requires HTTPS):
# SECURE_SSL_REDIRECT = True
# SESSION_COOKIE_SECURE = True
# CSRF_COOKIE_SECURE = True
# SECURE_HSTS_SECONDS = 31536000

# ─────────────────────────────────────────────────────────────────────────────
# Logging — see errors clearly in development
# ─────────────────────────────────────────────────────────────────────────────

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
        },
        "ai_chat": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
        "transactions": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
        "fraud": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}
