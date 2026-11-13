import time

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.ai.providers.base import LLMError
from apps.ai.providers.registry import get_provider


class Command(BaseCommand):
    help = "Check karta hai ki AI provider (ya apna model) chal raha hai aur kitna dheema hai."

    def handle(self, *args, **opts):
        self.stdout.write(
            f"Provider: {settings.LLM_PROVIDER}   Model: {settings.LLM_MODEL or '(default)'}"
        )
        try:
            provider = get_provider()
            start = time.monotonic()
            result = provider.complete(
                system="Reply with one short friendly sentence in Hinglish.",
                messages=[{"role": "user", "content": "Namaste, aap kaise hain?"}],
                max_tokens=60,
            )
        except LLMError as exc:
            self.stdout.write(f"[FIX] Nahi chala: {exc}")
            return
        took = time.monotonic() - start
        self.stdout.write(f"[OK]  {took:.1f} second me jawab aaya: {result.text.strip()}")
        if took > settings.LLM_TIMEOUT * 0.7:
            self.stdout.write("      Dheema hai. LLM_TIMEOUT badhao ya chhota model lo.")
