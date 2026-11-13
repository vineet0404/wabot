import json
import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.ai.prompt import build_messages, build_system_prompt
from apps.ai.service import HANDOVER_MARKER, UNKNOWN_MARKER
from apps.core.models import Message, Tenant

PHONE_LIKE = re.compile(r"\+?\d[\d\s\-]{7,}\d")
FLAG_TO_MARKER = {"unknown": UNKNOWN_MARKER, "handover": HANDOVER_MARKER}


def mask(text: str) -> str:
    return PHONE_LIKE.sub("[NUMBER]", text)


class Command(BaseCommand):
    help = (
        "Ek business ki asli chats ko fine-tuning format me nikalta hai (phone number masked). "
        "Naam aur baaki private baatein haath se dekh kar hatani padengi."
    )

    def add_arguments(self, parser):
        parser.add_argument("--tenant", type=int, required=True)
        parser.add_argument("--out", default="finetune/data/real_export.jsonl")
        parser.add_argument(
            "--only-flag",
            choices=["unknown", "handover", "error", "budget"],
            help="Sirf wo jawab jahan bot atka tha (inhe tum sahi jawab se badal sakte ho)",
        )
        parser.add_argument(
            "--i-have-consent",
            action="store_true",
            help="Maine customers aur business owner se is data ke use ki ijazat le li hai",
        )

    def handle(self, *args, **opts):
        if not opts["i_have_consent"]:
            raise CommandError(
                "Asli customer chats par training ke liye pehle unki aur business owner ki "
                "ijazat chahiye (DPDP). Ijazat ho to --i-have-consent lagao."
            )
        tenant = Tenant.objects.filter(pk=opts["tenant"]).first()
        if tenant is None:
            raise CommandError("Ye tenant nahi mila.")

        replies = Message.objects.filter(
            tenant=tenant, direction=Message.Direction.OUT, reply_to__isnull=False
        ).select_related("reply_to")
        if opts["only_flag"]:
            replies = replies.filter(flag=opts["only_flag"])

        system = build_system_prompt(tenant)
        count = 0
        out = Path(opts["out"])
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8") as f:
            for reply in replies.order_by("id"):
                history = build_messages(reply.reply_to)
                if not history:
                    continue
                target = FLAG_TO_MARKER.get(reply.flag, reply.body)
                messages = [
                    {"role": "system", "content": system},
                    *({"role": m["role"], "content": mask(m["content"])} for m in history),
                    {"role": "assistant", "content": target},
                ]
                record = {
                    "messages": messages,
                    "meta": {"message_id": reply.pk, "flag": reply.flag},
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                count += 1

        self.stdout.write(f"{count} examples save hue: {out}")
        self.stdout.write(
            "DHYAN: ye bot ke apne jawab hain, kuch galat bhi honge. Har line padho, galat jawab "
            "sahi karo, naam jaisi private baatein hatao, aur tabhi training me daalo."
        )
