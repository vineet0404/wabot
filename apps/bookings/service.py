"""Owner ke faisle (confirm/mana) ko customer tak pahunchana."""

import logging

from django.utils import timezone

from apps.core.models import Message
from apps.whatsapp.client import WhatsAppError, send_template, send_text

from .models import Booking

logger = logging.getLogger(__name__)

SENT, NOT_SENT, DRY_RUN = "sent", "not_sent", "dry_run"


def window_open(conversation) -> bool:
    return bool(conversation.window_expires_at and conversation.window_expires_at > timezone.now())


def _record_out(booking, text, wa_id, flag="booking"):
    Message.objects.create(
        tenant=booking.tenant,
        conversation=booking.conversation,
        direction=Message.Direction.OUT,
        type="text",
        body=text,
        wa_message_id=wa_id,
        flag=flag,
    )


def confirm_text(booking) -> str:
    return (
        f"Aapka appointment {booking.when_text()} ke liye confirm hai. "
        f"- {booking.tenant.name}. Badlav ho to yahin batayein."
    )


def reject_text(booking) -> str:
    return (
        f"Maaf kijiye, {booking.when_text()} ka slot available nahi hai. "
        "Kripya koi aur din ya samay batayein."
    )


def confirm_booking(booking) -> str:
    """Confirm karo aur customer ko batao. 'sent' ya 'not_sent' (window band, template nahi)."""
    booking.status = Booking.Status.CONFIRMED
    booking.decided_at = timezone.now()
    booking.save(update_fields=["status", "decided_at"])
    return _notify_customer(booking, confirm_text(booking), booking.tenant.confirm_template)


def reject_booking(booking) -> str:
    booking.status = Booking.Status.REJECTED
    booking.decided_at = timezone.now()
    booking.save(update_fields=["status", "decided_at"])
    return _notify_customer(booking, reject_text(booking), "")


def cancel_booking(booking) -> None:
    booking.status = Booking.Status.CANCELLED
    booking.decided_at = timezone.now()
    booking.save(update_fields=["status", "decided_at"])


def template_params(booking) -> list[str]:
    """Template body ke {{1}} naam, {{2}} samay, {{3}} business ka naam."""
    return [booking.display_name, booking.when_text(), booking.tenant.name]


def _notify_customer(booking, text, template_name) -> str:
    phone = booking.customer.phone
    if not booking.tenant.wa_access_token:
        # Test mode: message sirf log me jata hai, asli customer ko nahi
        send_text(booking.tenant, phone, text)
        return DRY_RUN
    try:
        if window_open(booking.conversation):
            wa_id = send_text(booking.tenant, phone, text)
            _record_out(booking, text, wa_id)
            return SENT
        if template_name:
            wa_id = send_template(booking.tenant, phone, template_name, template_params(booking))
            _record_out(booking, f"[template {template_name}] {text}", wa_id)
            return SENT
    except WhatsAppError as exc:
        logger.warning("booking %s: customer ko message nahi gaya: %s", booking.pk, exc)
    return NOT_SENT
