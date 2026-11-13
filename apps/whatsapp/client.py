import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class WhatsAppError(Exception):
    pass


def mask_phone(phone: str) -> str:
    """Logs me poora number nahi, sirf aakhri 4 digit."""
    return "*" * max(len(phone) - 4, 0) + phone[-4:]


def send_text(tenant, to: str, body: str) -> str | None:
    """Text message bhejta hai. Token nahi hai to sirf log karta hai (dry-run)."""
    if not tenant.wa_access_token:
        logger.info(
            "dry-run: tenant=%s to=%s chars=%d (token nahi hai, message nahi bheja)",
            tenant.pk,
            mask_phone(to),
            len(body),
        )
        return None

    url = (
        f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}"
        f"/{tenant.wa_phone_number_id}/messages"
    )
    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {tenant.wa_access_token}"},
        json={
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": body},
        },
        timeout=10,
    )
    if response.status_code >= 400:
        raise WhatsAppError(f"Meta ne {response.status_code} diya: {response.text[:200]}")
    data = response.json()
    return (data.get("messages") or [{}])[0].get("id")


def mark_read(tenant, wa_message_id: str, typing: bool = True) -> None:
    """Customer ke message par blue tick lagata hai, aur chahe to "typing..." dikhata hai.

    Typing ~25 second ya hamara jawab jaane tak dikhti hai. Token nahi hai to kuch nahi karta.
    Ye request Meta ke docs se (third-party mirror ke zariye) li gayi hai, apne account par
    pehli baar chalake dekhna. Fail hone par WhatsAppError uthta hai; bulane wala ise ignore kare.
    """
    if not tenant.wa_access_token or not wa_message_id:
        return
    payload = {"messaging_product": "whatsapp", "status": "read", "message_id": wa_message_id}
    if typing:
        payload["typing_indicator"] = {"type": "text"}
    url = (
        f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}"
        f"/{tenant.wa_phone_number_id}/messages"
    )
    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {tenant.wa_access_token}"},
        json=payload,
        timeout=5,
    )
    if response.status_code >= 400:
        raise WhatsAppError(
            f"mark_read: Meta ne {response.status_code} diya: {response.text[:150]}"
        )


def send_template(tenant, to: str, name: str, params: list[str], lang: str | None = None):
    """Approved template message bhejta hai (24 ghante ki window ke bahar bhi chalta hai).

    params body ke {{1}}, {{2}}... me jaate hain. Token nahi hai to dry-run.
    """
    if not tenant.wa_access_token:
        logger.info(
            "dry-run template %s: tenant=%s to=%s (token nahi hai)", name, tenant.pk, mask_phone(to)
        )
        return None
    url = (
        f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}"
        f"/{tenant.wa_phone_number_id}/messages"
    )
    template = {"name": name, "language": {"code": lang or tenant.template_lang}}
    if params:
        template["components"] = [
            {"type": "body", "parameters": [{"type": "text", "text": p} for p in params]}
        ]
    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {tenant.wa_access_token}"},
        json={"messaging_product": "whatsapp", "to": to, "type": "template", "template": template},
        timeout=10,
    )
    if response.status_code >= 400:
        raise WhatsAppError(f"Meta ne {response.status_code} diya: {response.text[:200]}")
    return (response.json().get("messages") or [{}])[0].get("id")
