"""Appointment se pehle customer ko yaad dilana. Har 10 minute me beat se chalta hai."""

import logging
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

from apps.core.models import Message
from apps.core.tasks import queue_owner_notification
from apps.whatsapp.client import WhatsAppError, send_template, send_text

from .models import Booking
from .service import template_params, window_open

logger = logging.getLogger(__name__)

MAX_LOOKAHEAD_HOURS = 72


def reminder_text(booking) -> str:
    return (
        f"Namaste {booking.display_name}, yaad dilane ke liye: aapka appointment "
        f"{booking.when_text()} ko {booking.tenant.name} me hai. Badlav ho to yahin batayein."
    )


def in_quiet_hours(tenant, now) -> bool:
    hour = now.astimezone(ZoneInfo(tenant.timezone)).hour
    return not (settings.REMINDER_QUIET_BEFORE_HOUR <= hour < settings.REMINDER_QUIET_AFTER_HOUR)


def due_bookings(now):
    rows = Booking.objects.filter(
        status=Booking.Status.CONFIRMED,
        reminder_sent_at__isnull=True,
        starts_at__gt=now,
        starts_at__lte=now + timedelta(hours=MAX_LOOKAHEAD_HOURS),
        tenant__is_active=True,
        tenant__reminder_hours_before__gt=0,
    ).select_related("tenant", "customer", "conversation")
    return [b for b in rows if b.starts_at <= now + timedelta(hours=b.tenant.reminder_hours_before)]


def send_due_reminders(now=None) -> dict:
    """Jin appointments ka reminder ka samay aa gaya unko bhejta hai. Counts lautata hai."""
    now = now or timezone.now()
    counts = {"sent": 0, "skipped": 0, "failed": 0, "quiet": 0}
    for booking in due_bookings(now):
        tenant = booking.tenant
        if in_quiet_hours(tenant, now):
            counts["quiet"] += 1
            continue

        # Pehle "claim" karo, taaki do baar chalne par do reminder na jayen
        claimed = Booking.objects.filter(pk=booking.pk, reminder_sent_at__isnull=True).update(
            reminder_sent_at=now
        )
        if not claimed:
            continue

        try:
            result = _deliver(booking)
        except WhatsAppError as exc:
            logger.warning("reminder fail booking=%s: %s", booking.pk, exc)
            Booking.objects.filter(pk=booking.pk).update(reminder_sent_at=None)  # agli baar retry
            counts["failed"] += 1
            continue

        Booking.objects.filter(pk=booking.pk).update(reminder_result=result)
        counts[result] += 1
        if result == "skipped":
            queue_owner_notification(
                tenant,
                f"{tenant.name}: {booking.display_name} ({booking.when_text()}) ko reminder nahi "
                "ja saka (24 ghante ki window band, reminder template set nahi). Khud bata dein.",
            )
    return counts


def _deliver(booking) -> str:
    tenant, phone = booking.tenant, booking.customer.phone
    if window_open(booking.conversation):
        text = reminder_text(booking)
        wa_id = send_text(tenant, phone, text)
    elif tenant.reminder_template:
        text = f"[template {tenant.reminder_template}] {reminder_text(booking)}"
        wa_id = send_template(tenant, phone, tenant.reminder_template, template_params(booking))
    else:
        return "skipped"
    Message.objects.create(
        tenant=tenant,
        conversation=booking.conversation,
        direction=Message.Direction.OUT,
        type="text",
        body=text,
        wa_message_id=wa_id,
        flag="reminder",
    )
    return "sent"
