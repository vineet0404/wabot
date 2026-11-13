import logging

from celery import shared_task

from .models import Tenant
from .notify import NotifyError, notify_owner

logger = logging.getLogger(__name__)


@shared_task(autoretry_for=(NotifyError,), retry_backoff=True, max_retries=3)
def notify_owner_task(tenant_id: int, text: str):
    tenant = Tenant.objects.filter(pk=tenant_id).first()
    if tenant is None:
        return "skipped: tenant nahi mila"
    sent = notify_owner(tenant, text)
    return f"sent: {','.join(sent) or 'koi channel set nahi'}"


def queue_owner_notification(tenant, text: str) -> None:
    """Message queue me daalta hai. Kuch bhi bigde to jawab/booking kabhi na rukey."""
    try:
        notify_owner_task.delay(tenant.pk, text)
    except Exception:
        logger.exception("owner notification queue nahi hui")
