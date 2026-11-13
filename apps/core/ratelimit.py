import logging

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


def client_ip(request) -> str:
    """Asli client ka IP. Proxy ke headers sirf tab maane jaate hain jab TRUST_PROXY_HEADERS=1."""
    if settings.TRUST_PROXY_HEADERS:
        cloudflare = request.META.get("HTTP_CF_CONNECTING_IP")
        if cloudflare:
            return cloudflare.strip()
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def count(key: str) -> int:
    try:
        return int(cache.get(key, 0))
    except Exception:  # Redis band ho to site na ruke
        logger.warning("rate-limit cache nahi mila, check skip hua")
        return 0


def add_failure(key: str, window: int) -> int:
    try:
        cache.add(key, 0, timeout=window)
        return cache.incr(key)
    except Exception:
        logger.warning("rate-limit cache nahi mila, failure count nahi hua")
        return 0


def reset(key: str) -> None:
    try:
        cache.delete(key)
    except Exception:
        pass
