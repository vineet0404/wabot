import time
import uuid

from django.core.management.base import BaseCommand, CommandError

from apps.core.models import Message, Tenant
from apps.whatsapp.services import process_payload
from apps.whatsapp.tasks import handle_inbound_message


class Command(BaseCommand):
    help = "Meta ke bina local me customer ka WhatsApp message simulate karta hai."

    def add_arguments(self, parser):
        parser.add_argument("text", help="Customer ka message")
        parser.add_argument("--tenant", type=int, help="Tenant id (nahi diya to pehla tenant)")
        parser.add_argument("--from", dest="sender", default="919800000001", help="Customer number")

    def handle(self, *args, **opts):
        tenants = Tenant.objects.order_by("id")
        tenant = tenants.filter(pk=opts["tenant"]).first() if opts["tenant"] else tenants.first()
        if tenant is None:
            raise CommandError("Pehle admin panel me ek Tenant banao.")

        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "metadata": {"phone_number_id": tenant.wa_phone_number_id},
                                "contacts": [
                                    {"wa_id": opts["sender"], "profile": {"name": "Test Customer"}}
                                ],
                                "messages": [
                                    {
                                        "from": opts["sender"],
                                        "id": f"sim.{uuid.uuid4().hex}",
                                        "type": "text",
                                        "text": {"body": opts["text"]},
                                    }
                                ],
                            }
                        }
                    ]
                }
            ]
        }
        # Webhook wala hi code path, bas signature wala step skip hota hai.
        ids = process_payload(payload)
        if not ids:
            self.stdout.write("Message save nahi hua (shayad tenant inactive hai).")
            return
        for message_id in ids:
            handle_inbound_message.delay(message_id)

        inbound = Message.objects.get(pk=ids[0])
        self.stdout.write(f"Tenant: {tenant.name}")
        self.stdout.write(f"  [in]  {inbound.body}")

        # Worker alag process me chalta hai, isliye reply aane ka thoda intezaar karte hain.
        deadline = time.monotonic() + 15
        reply = None
        while time.monotonic() < deadline:
            reply = (
                Message.objects.filter(
                    conversation=inbound.conversation,
                    direction=Message.Direction.OUT,
                    id__gt=inbound.pk,
                )
                .order_by("id")
                .first()
            )
            if reply:
                break
            time.sleep(0.5)

        if reply:
            self.stdout.write(f"  [out] {reply.body}")
        else:
            self.stdout.write(
                "  [out] reply 15 second me nahi aaya. Worker chal raha hai? Ye chalao:\n"
                "        docker compose logs worker --tail 30"
            )
