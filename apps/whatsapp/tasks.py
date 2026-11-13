import logging

import requests
from celery import shared_task
from django.utils import timezone

from apps.ai.service import Reply, generate_reply
from apps.bookings.tasks import queue_booking_extraction
from apps.core.models import Conversation, Message
from apps.core.notify import inbox_link
from apps.core.tasks import queue_owner_notification

from .client import WhatsAppError, mark_read, mask_phone, send_text

logger = logging.getLogger(__name__)

NON_TEXT_REPLY = "Abhi main sirf text message samajh sakta hoon."


@shared_task(
    bind=True,
    autoretry_for=(WhatsAppError, requests.RequestException),
    retry_backoff=True,
    max_retries=3,
)
def handle_inbound_message(self, message_id: int):
    """Customer ka message aaya: AI se jawab banao aur bhejo."""
    message = Message.objects.select_related("conversation__customer", "tenant").get(pk=message_id)
    conversation = message.conversation

    if conversation.state == Conversation.State.HUMAN:
        return "skipped: owner sambhal raha hai"
    if Message.objects.filter(reply_to=message).exists():
        return "skipped: jawab pehle hi ja chuka hai"

    # Blue tick + typing turant. Ye fail ho to bhi jawab rukna nahi chahiye.
    try:
        mark_read(message.tenant, message.wa_message_id)
    except Exception as exc:
        logger.warning("read receipt/typing nahi gaya: %s", exc)

    if message.type == "text":
        reply = generate_reply(message)
    else:
        reply = Reply(NON_TEXT_REPLY)

    wa_id = send_text(message.tenant, conversation.customer.phone, reply.text)
    Message.objects.create(
        tenant=message.tenant,
        conversation=conversation,
        direction=Message.Direction.OUT,
        type="text",
        body=reply.text,
        wa_message_id=wa_id,
        flag=reply.flag,
        reply_to=message,
        llm_ms=reply.llm_ms,
        total_ms=int((timezone.now() - message.created_at).total_seconds() * 1000),
    )

    if message.type == "text" and reply.flag == "":
        queue_booking_extraction(message)

    if reply.flag == "handover":
        conversation.state = Conversation.State.HUMAN
        conversation.save(update_fields=["state"])
        customer = conversation.customer
        who = customer.name or mask_phone(customer.phone)
        queue_owner_notification(
            message.tenant,
            f"{message.tenant.name}: {who} ko aapki zaroorat hai (bot ne handover kiya).\n"
            f"Inbox: {inbox_link(conversation)}",
        )
    return f"replied ({reply.flag or 'ok'})"
