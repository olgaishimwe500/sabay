"""Production overrides; select with DJANGO_SETTINGS_MODULE."""

import os

from .settings import *  # noqa: F403

SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
DEBUG = False
ALLOWED_HOSTS = ["sabay.org", "www.sabay.org"]
CSRF_TRUSTED_ORIGINS = ["https://sabay.org", "https://www.sabay.org"]
STATIC_ROOT = Path(os.environ["DJANGO_STATIC_ROOT"])  # noqa: F405
DATABASES["default"]["NAME"] = os.environ["DJANGO_DB_PATH"]  # noqa: F405
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 3600
# Opt into subdomain HSTS and preload only after auditing every subdomain.
# These are deliberate rollout choices; keep all other deploy warnings fatal.
SILENCED_SYSTEM_CHECKS = ["security.W005", "security.W021"]
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [{"address": "redis://127.0.0.1:6379", "socket_timeout": None}],
        },
    }
}
