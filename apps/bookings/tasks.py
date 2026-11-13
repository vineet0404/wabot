import logging

from celery import shared_task

from apps.core.models import Message
from apps.core.notify import bookings_link
from apps.core.tasks import queue_owner_notification

from .extract import extract_booking

logger = logging.getLogger(__name__)


@shared_task
def extract_booking_task(message_id: int):
    message = Message.objects.select_related("conversation__customer", "tenant").get(pk=message_id)
    booking, changed = extract_booking(message)
    if booking is None or not changed:
        return "no new booking"
    queue_owner_notification(
        booking.tenant,
        f"{booking.tenant.name}: {booking.display_name} ne appointment maangi: "
        f"{booking.when_text()}.\nConfirm karo: {bookings_link()}",
    )
    return f"booking {booking.pk} requested"


def queue_booking_extraction(message) -> None:
    """Jawab jaane ke baad background me. Kuch bigde to jawab par asar nahi."""
    try:
        extract_booking_task.delay(message.pk)
    except Exception:
        logger.exception("booking extraction queue nahi hui")


@shared_task
def send_due_reminders_task():
    from .reminders import send_due_reminders

    return send_due_reminders()
