import logging
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.models import Conversation, Customer, Message, Tenant

logger = logging.getLogger(__name__)


def process_payload(payload: dict) -> list[int]:
    """Meta ke webhook payload se naye messages save karta hai. Naye message ids lautata hai."""
    new_ids: list[int] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            raw_messages = value.get("messages") or []
            if not raw_messages:
                continue  # delivery status wagairah, abhi zarurat nahi

            phone_number_id = (value.get("metadata") or {}).get("phone_number_id")
            tenant = Tenant.objects.filter(
                wa_phone_number_id=phone_number_id, is_active=True
            ).first()
            if tenant is None:
                logger.warning("Anjaan phone_number_id=%s, message chhoda", phone_number_id)
                continue

            names = {
                c.get("wa_id"): (c.get("profile") or {}).get("name", "")
                for c in value.get("contacts", [])
            }
            for raw in raw_messages:
                message = store_inbound(tenant, raw, names)
                if message is not None:
                    new_ids.append(message.pk)
    return new_ids


def store_inbound(tenant: Tenant, raw: dict, names: dict) -> Message | None:
    wa_id = raw.get("id")
    sender = raw.get("from")
    if not wa_id or not sender:
        return None

    message_type = raw.get("type", "unknown")
    body = (raw.get("text") or {}).get("body", "") if message_type == "text" else ""

    customer, _ = Customer.objects.get_or_create(
        tenant=tenant, phone=sender, defaults={"name": names.get(sender, "")}
    )
    conversation, _ = Conversation.objects.get_or_create(
        tenant=tenant, customer=customer, channel="whatsapp"
    )

    try:
        with transaction.atomic():
            message = Message.objects.create(
                tenant=tenant,
                conversation=conversation,
                direction=Message.Direction.IN,
                type=message_type,
                body=body,
                wa_message_id=wa_id,
            )
    except IntegrityError:
        logger.info("Dobara aaya message, ignore kiya")
        return None

    now = timezone.now()
    conversation.last_message_at = now
    conversation.window_expires_at = now + timedelta(hours=24)
    conversation.save(update_fields=["last_message_at", "window_expires_at"])
    return message
