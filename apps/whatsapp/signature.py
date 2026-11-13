import hashlib
import hmac


def verify_signature(app_secret: str, body: bytes, header: str | None) -> bool:
    """Meta har webhook par X-Hub-Signature-256 bhejta hai. Galat ho to request nakli hai."""
    if not app_secret or not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256="))
