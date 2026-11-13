import base64
import hashlib
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from .database import parse_database_url

BASE_DIR = Path(__file__).resolve().parent.parent


def env(name, default=""):
    return os.getenv(name, default)


def env_bool(name, default=False):
    return env(name, "1" if default else "0").lower() in ("1", "true", "yes")


SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-only-change-me")
DEBUG = env_bool("DJANGO_DEBUG", True)

if not DEBUG and SECRET_KEY.startswith("dev-only"):
    raise ImproperlyConfigured("Production me DJANGO_SECRET_KEY zaroor badlo.")

# Tunnel ke hosts sirf development me allowed hain.
# Production me DJANGO_ALLOWED_HOSTS me apna domain do.
_default_hosts = "localhost,127.0.0.1"
if DEBUG:
    _default_hosts += ",.trycloudflare.com,.ngrok-free.app,.ngrok-free.dev,.ngrok.io"
ALLOWED_HOSTS = [
    h.strip() for h in env("DJANGO_ALLOWED_HOSTS", _default_hosts).split(",") if h.strip()
]

# Admin ka raasta. Random rakhoge (jaise "panel-x7k2/") to bots seedha /admin/ par nahi aayenge.
ADMIN_URL = env("ADMIN_URL", "admin/")
if not ADMIN_URL.endswith("/"):
    ADMIN_URL += "/"

# Proxy ya tunnel ke peeche ho to 1 karo, tabhi asli client IP headers se padha jayega.
TRUST_PROXY_HEADERS = env_bool("TRUST_PROXY_HEADERS", False)

# Tokens ko database me encrypt karne ki key. Banane ka tareeka .env.example me hai.
FIELD_ENCRYPTION_KEY = env("FIELD_ENCRYPTION_KEY")
if not FIELD_ENCRYPTION_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("Production me FIELD_ENCRYPTION_KEY zaroor set karo.")
    FIELD_ENCRYPTION_KEY = base64.urlsafe_b64encode(
        hashlib.sha256(SECRET_KEY.encode()).digest()
    ).decode()

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.core",
    "apps.whatsapp",
    "apps.ai",
    "apps.knowledge",
    "apps.bookings",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # admin ki static files bina nginx ke
    "apps.core.middleware.AdminLoginThrottleMiddleware",
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

# Database: DATABASE_URL de do to koi bhi supported DB chalega (config/database.py dekho).
# Nahi diya to purane POSTGRES_* settings use hoti hain.
if env("DATABASE_URL"):
    DATABASES = {"default": parse_database_url(env("DATABASE_URL"), BASE_DIR)}
elif env_bool("USE_SQLITE"):
    DATABASES = {
        "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("POSTGRES_DB", "wabot"),
            "USER": env("POSTGRES_USER", "wabot"),
            "PASSWORD": env("POSTGRES_PASSWORD", "wabot"),
            "HOST": env("POSTGRES_HOST", "localhost"),
            "PORT": env("POSTGRES_PORT", "5432"),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

if env_bool("USE_LOCMEM_CACHE"):
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": env("REDIS_URL", "redis://localhost:6379/0"),
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

# Security
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 8 * 60 * 60  # admin session 8 ghante me khatam
CSRF_COOKIE_HTTPONLY = True
DATA_UPLOAD_MAX_MEMORY_SIZE = 1_000_000  # webhook body 1 MB se bada nahi

if not DEBUG:
    # Ye sab tab lagta hai jab DJANGO_DEBUG=0 ho (live/production).
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("FORCE_HTTPS", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

META_APP_SECRET = env("META_APP_SECRET")
META_VERIFY_TOKEN = env("META_VERIFY_TOKEN")
WHATSAPP_API_VERSION = env("WHATSAPP_API_VERSION", "v21.0")

# --- AI provider (docs/AI_PROVIDERS.md dekho) ---
# fake | claude | openai | groq | together | openrouter | gemini | ollama | openai_compatible
# ya apni class ka path (package.module.Class)
LLM_PROVIDER = env("LLM_PROVIDER", "fake")
LLM_BASE_URL = env("LLM_BASE_URL")
LLM_API_KEY = env("LLM_API_KEY")
LLM_MODEL = env("LLM_MODEL")
LLM_TIMEOUT = int(env("LLM_TIMEOUT", "30"))
# 429/5xx par kitni baar dobara koshish (har baar thoda ruk kar)
LLM_RETRIES = int(env("LLM_RETRIES", "2"))
LLM_MAX_OUTPUT_TOKENS = int(env("LLM_MAX_OUTPUT_TOKENS", "300"))
# Kuch naye OpenAI models "max_completion_tokens" maangte hain
LLM_MAX_TOKENS_PARAM = env("LLM_MAX_TOKENS_PARAM", "max_tokens")
# Khali chhodo to temperature bheji hi nahi jati (kuch models ise nahi maante)
LLM_TEMPERATURE = env("LLM_TEMPERATURE", "")
LLM_ANTHROPIC_VERSION = env("LLM_ANTHROPIC_VERSION", "2023-06-01")
LLM_HISTORY_MESSAGES = int(env("LLM_HISTORY_MESSAGES", "10"))
# Har business ke liye roz ke kul tokens (input + output). 0 = koi limit nahi
LLM_DAILY_TOKEN_BUDGET = int(env("LLM_DAILY_TOKEN_BUDGET", "100000"))

CELERY_BROKER_URL = env("REDIS_URL", "redis://localhost:6379/0")
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", False)
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TASK_ACKS_LATE = True

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simple": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "simple"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}

# --- Knowledge base / RAG (docs/GO_LIVE.md) ---
# none = sirf keyword search (bina kisi API ke). Behtar search ke liye embedding provider lagao:
# openai | ollama | local | gemini | together | openai_compatible
EMBED_PROVIDER = env("EMBED_PROVIDER", "none")
EMBED_BASE_URL = env("EMBED_BASE_URL")
EMBED_API_KEY = env("EMBED_API_KEY")
EMBED_MODEL = env("EMBED_MODEL")
EMBED_TIMEOUT = int(env("EMBED_TIMEOUT", "15"))
KB_TOP_K = int(env("KB_TOP_K", "4"))
KB_MIN_SCORE = float(env("KB_MIN_SCORE", "0.3"))

# --- Owner notification aur booking (docs/BOOKING_AND_REMINDERS.md) ---
# Inbox ke links ke liye. Production me apna https domain, jaise https://bot.aapkadomain.in
PUBLIC_BASE_URL = env("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
# Telegram: @BotFather se bot banao, uska token yahan. Khali = Telegram notification band.
TELEGRAM_BOT_TOKEN = env("TELEGRAM_BOT_TOKEN")
# Email: console = sirf logs me dikhta hai (dev). Asli email ke liye SMTP bharo.
EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend"
    if DEBUG
    else "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = env("EMAIL_HOST")
EMAIL_PORT = int(env("EMAIL_PORT", "587"))
EMAIL_HOST_USER = env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER or "wabot@localhost")
# Reminder sirf is samay ke beech bhejte hain (tenant ka local time, ghante)
REMINDER_QUIET_BEFORE_HOUR = int(env("REMINDER_QUIET_BEFORE_HOUR", "8"))
REMINDER_QUIET_AFTER_HOUR = int(env("REMINDER_QUIET_AFTER_HOUR", "21"))
