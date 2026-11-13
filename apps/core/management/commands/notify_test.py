from django.core.management.base import BaseCommand, CommandError

from apps.core.models import Tenant
from apps.core.notify import NotifyError, configured_channels, notify_owner


class Command(BaseCommand):
    help = "Owner notification (Telegram/email) chalti hai ya nahi, ek test sandesh bhejkar dekho."

    def add_arguments(self, parser):
        parser.add_argument("--tenant", type=int, default=0)

    def handle(self, *args, **opts):
        qs = Tenant.objects.order_by("id")
        tenant = qs.filter(pk=opts["tenant"]).first() if opts["tenant"] else qs.first()
        if tenant is None:
            raise CommandError("Tenant nahi mila")
        channels = configured_channels(tenant)
        if not channels:
            self.stdout.write(
                "[FIX] Koi channel set nahi. Admin me Tenant ka notify_email ya "
                "notify_telegram_chat_id bharo (Telegram ke liye .env me TELEGRAM_BOT_TOKEN bhi)."
            )
            return
        try:
            sent = notify_owner(
                tenant, f"{tenant.name}: yeh ek test sandesh hai. Sab theek chal raha hai."
            )
        except NotifyError:
            self.stdout.write(
                f"[FIX] {', '.join(channels)} set hai par bhej nahi paye. Logs dekho."
            )
            return
        self.stdout.write(f"[OK] Bheja gaya: {', '.join(sent)}")
