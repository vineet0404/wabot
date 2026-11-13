import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.core.models import Tenant


class Command(BaseCommand):
    help = "Real WhatsApp number par message bhejta hai (Meta ka hello_world template ya text)."

    def add_arguments(self, parser):
        parser.add_argument("to", help="Country code ke saath number, jaise 919876543210")
        parser.add_argument(
            "--text",
            help="Text bhejo. Sirf tab chalega jab customer ne pichle 24 ghante me likha ho.",
        )
        parser.add_argument("--tenant", type=int)

    def handle(self, *args, **opts):
        qs = Tenant.objects.order_by("id")
        tenant = qs.filter(pk=opts["tenant"]).first() if opts["tenant"] else qs.first()
        if tenant is None or not tenant.wa_access_token:
            raise CommandError("Tenant ya uska access token nahi mila. Admin me bharo.")

        if opts["text"]:
            body = {"type": "text", "text": {"body": opts["text"]}}
        else:
            # Pehla message hamesha template se jaata hai (24 ghante wali window band hoti hai).
            body = {
                "type": "template",
                "template": {"name": "hello_world", "language": {"code": "en_US"}},
            }

        r = requests.post(
            f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}"
            f"/{tenant.wa_phone_number_id}/messages",
            headers={"Authorization": f"Bearer {tenant.wa_access_token}"},
            json={"messaging_product": "whatsapp", "to": opts["to"], **body},
            timeout=10,
        )
        self.stdout.write(f"Meta status: {r.status_code}")
        self.stdout.write(r.text[:400])
