"""Owner ko sandesh bhejta hai (Telegram aur/ya email). Customer ka message ismein nahi bhejte."""

import logging

import requests
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


class NotifyError(Exception):
    """Jitne channels set hain, sab fail hue."""


def configured_channels(tenant) -> list[str]:
    channels = []
    if tenant.notify_telegram_chat_id and settings.TELEGRAM_BOT_TOKEN:
        channels.append("telegram")
    if tenant.notify_email:
        channels.append("email")
    return channels


def _send_telegram(tenant, text: str) -> None:
    response = requests.post(
        f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
        json={"chat_id": tenant.notify_telegram_chat_id, "text": text},
        timeout=10,
    )
    if response.status_code >= 400:
        # Token URL me hota hai, isliye URL kabhi log nahi karte
        raise RuntimeError(f"Telegram ne {response.status_code} diya: {response.text[:150]}")


def _send_email(tenant, text: str) -> None:
    send_mail(
        subject=f"[{tenant.name}] Aapki zaroorat hai",
        message=text,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[tenant.notify_email],
        fail_silently=False,
    )


def notify_owner(tenant, text: str) -> list[str]:
    """Set kiye hue sab channels par bhejta hai. Kaam kiye hue channels ki list deta hai.

    Koi channel set nahi to khali list. Set the par sab fail hue to NotifyError.
    """
    channels = configured_channels(tenant)
    sent = []
    for name in channels:
        try:
            {"telegram": _send_telegram, "email": _send_email}[name](tenant, text)
            sent.append(name)
        except Exception as exc:  # ek channel girne se doosra na ruke
            logger.warning(
                "notify %s fail (tenant=%s): %s", name, tenant.pk, exc.__class__.__name__
            )
    if channels and not sent:
        raise NotifyError("koi bhi notification channel nahi chala")
    return sent


def bookings_link() -> str:
    return f"{settings.PUBLIC_BASE_URL}/inbox/bookings/"


def inbox_link(conversation) -> str:
    return f"{settings.PUBLIC_BASE_URL}/inbox/{conversation.pk}/"
