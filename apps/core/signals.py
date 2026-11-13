import logging

from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver

from .middleware import LOGIN_WINDOW, ip_key, user_key
from .ratelimit import add_failure, client_ip, reset

logger = logging.getLogger("security")


@receiver(user_login_failed)
def on_login_failed(sender, credentials, request=None, **kwargs):
    username = (credentials or {}).get("username", "")
    ip = client_ip(request) if request is not None else "unknown"
    add_failure(ip_key(ip), LOGIN_WINDOW)
    if username:
        add_failure(user_key(username), LOGIN_WINDOW)
    logger.warning("login fail: user=%s ip=%s", username[:50], ip)


@receiver(user_logged_in)
def on_login_ok(sender, request, user, **kwargs):
    reset(user_key(user.get_username()))
    reset(ip_key(client_ip(request)))
    logger.info("login ok: user=%s ip=%s", user.get_username(), client_ip(request))
