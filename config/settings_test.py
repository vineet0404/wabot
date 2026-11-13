from .settings import *  # noqa: F401,F403

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}

CELERY_TASK_ALWAYS_EAGER = True
META_APP_SECRET = "test-app-secret"
META_VERIFY_TOKEN = "test-verify-token"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
LLM_PROVIDER = "fake"
LLM_DAILY_TOKEN_BUDGET = 100000
