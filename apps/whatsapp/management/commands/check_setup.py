import requests
from django.conf import settings
from django.core.management.base import BaseCommand

from apps.core.models import Tenant
from apps.knowledge.models import KnowledgeChunk


class Command(BaseCommand):
    help = "Real WhatsApp testing se pehle check karta hai ki sab kuch set hai ya nahi."

    def line(self, ok, text):
        self.stdout.write(("[OK]   " if ok else "[FIX]  ") + text)

    def handle(self, *args, **opts):
        self.line(bool(settings.META_APP_SECRET), "META_APP_SECRET (.env me)")
        self.line(
            bool(settings.META_VERIFY_TOKEN)
            and settings.META_VERIFY_TOKEN != "change-me-to-a-random-string",
            "META_VERIFY_TOKEN badla hua hai",
        )

        tenants = Tenant.objects.filter(is_active=True)
        self.line(tenants.exists(), f"Active tenant (admin me): {tenants.count()}")

        for tenant in tenants:
            if not tenant.wa_access_token:
                self.line(False, f"{tenant.name}: access token khali hai (dry-run mode)")
                continue
            url = (
                f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}"
                f"/{tenant.wa_phone_number_id}"
            )
            try:
                r = requests.get(
                    url,
                    params={"fields": "display_phone_number,verified_name"},
                    headers={"Authorization": f"Bearer {tenant.wa_access_token}"},
                    timeout=10,
                )
            except requests.RequestException as exc:
                self.line(
                    False, f"{tenant.name}: Meta tak nahi pahunch paya ({exc.__class__.__name__})"
                )
                continue
            if r.status_code == 200:
                data = r.json()
                self.line(
                    True,
                    f"{tenant.name}: token chal raha hai, "
                    f"number {data.get('display_phone_number')}",
                )
            else:
                self.line(
                    False,
                    f"{tenant.name}: Meta ne {r.status_code} diya. "
                    "Token expire ya phone_number_id galat. "
                    f"{r.text[:150]}",
                )

        self.go_live_checks(tenants)
        self.stdout.write("\nWebhook URL: https://<tunnel-host>/webhooks/whatsapp/")

    def go_live_checks(self, tenants):
        """Live jaane se pehle ki cheezein. Dev me [FIX] aana normal hai."""
        self.stdout.write("\n--- Go-live checks (dev me [FIX] aana theek hai) ---")
        self.line(not settings.DEBUG, "DJANGO_DEBUG=0")
        self.line(
            settings.LLM_PROVIDER != "fake",
            f"LLM_PROVIDER asli hai (abhi: {settings.LLM_PROVIDER}); 'fake' sirf echo karta hai",
        )
        self.line(settings.ADMIN_URL != "admin/", "ADMIN_URL badla hua hai")
        for tenant in tenants:
            has_info = bool(tenant.business_info.strip())
            chunks = KnowledgeChunk.objects.filter(tenant=tenant).count()
            self.line(
                has_info or chunks > 0,
                f"{tenant.name}: business info ya knowledge base bhara hai ({chunks} chunks)",
            )
            self.line(tenant.members.exists(), f"{tenant.name}: inbox ke liye members set hain")
            self.line(
                bool(tenant.notify_email or tenant.notify_telegram_chat_id),
                f"{tenant.name}: owner notification (email/Telegram) set hai",
            )
