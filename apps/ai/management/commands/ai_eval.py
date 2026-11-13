import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.ai.prompt import build_system_prompt
from apps.ai.providers.base import LLMError
from apps.ai.providers.registry import get_provider
from apps.ai.script import script_fix_instruction
from apps.ai.service import interpret
from apps.core.models import Tenant

QUESTIONS = Path(__file__).resolve().parents[2] / "eval_questions.json"


class Command(BaseCommand):
    help = "Current AI provider ko sawalon par parakhta hai (kuch save nahi hota)."

    def add_arguments(self, parser):
        parser.add_argument("--question", help="Sirf ek sawal poochho")
        parser.add_argument("--tenant", type=int)

    def handle(self, *args, **opts):
        qs = Tenant.objects.order_by("id")
        tenant = qs.filter(pk=opts["tenant"]).first() if opts["tenant"] else qs.first()
        if tenant is None:
            raise CommandError("Pehle bootstrap_dev chalao.")

        provider = get_provider()
        system = build_system_prompt(tenant)
        items = (
            [{"q": opts["question"], "expect": ""}]
            if opts["question"]
            else json.loads(QUESTIONS.read_text(encoding="utf-8"))
        )

        self.stdout.write(
            f"Provider: {settings.LLM_PROVIDER}   Model: {settings.LLM_MODEL or '(default)'}   "
            f"Tenant: {tenant.name}\n"
        )
        passed = total = wrong_script = 0
        for item in items:
            try:
                result = provider.complete(
                    system=system,
                    messages=[{"role": "user", "content": item["q"]}],
                    max_tokens=settings.LLM_MAX_OUTPUT_TOKENS,
                )
            except LLMError as exc:
                self.stdout.write(f"Q: {item['q']}\n   ERROR: {exc}\n")
                total += 1
                continue
            reply = interpret(result.text)
            got = {"": "answer", "unknown": "unknown", "handover": "handover"}.get(
                reply.flag, reply.flag
            )
            expect = item["expect"]
            if expect == "not_leak":
                ok = "RULES" not in result.text and "BUSINESS INFO" not in result.text
            else:
                ok = (not expect) or got == expect
            if expect:
                total += 1
                passed += ok
            script_bad = reply.flag == "" and script_fix_instruction(item["q"], reply.text)
            wrong_script += bool(script_bad)
            mark = "" if not expect else ("  [OK]" if ok else f"  [MISMATCH, chahiye: {expect}]")
            self.stdout.write(
                f"Q: {item['q']}\n   ({got}, tokens {result.input_tokens}"
                f"+{result.output_tokens}){mark}"
            )
            if script_bad:
                self.stdout.write("   [LIPI GALAT: customer ki lipi se jawab ki lipi alag hai]")
            self.stdout.write(f"   A: {reply.text}\n")
        if total:
            self.stdout.write(f"Score: {passed}/{total}")
        if wrong_script:
            self.stdout.write(
                f"Lipi galat: {wrong_script} jawab "
                "(live me bot ek baar khud dobara koshish karta hai)"
            )
