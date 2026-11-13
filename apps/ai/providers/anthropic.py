import requests
from django.conf import settings

from .base import LLMError, LLMProvider, LLMResult

DEFAULT_MODEL = "claude-haiku-5-5"


class AnthropicProvider(LLMProvider):
    """Claude (Anthropic) ka direct API. Koi extra library nahi chahiye."""

    def __init__(self):
        self.base_url = (settings.LLM_BASE_URL or "https://api.anthropic.com").rstrip("/")
        self.api_key = settings.LLM_API_KEY
        self.model = settings.LLM_MODEL or DEFAULT_MODEL
        if not self.api_key:
            raise LLMError("LLM_API_KEY set karo (Anthropic Console se key banao).")

    def complete(self, system: str, messages: list[dict], max_tokens: int) -> LLMResult:
        body = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": messages,
        }
        if settings.LLM_TEMPERATURE != "":
            body["temperature"] = float(settings.LLM_TEMPERATURE)
        try:
            response = requests.post(
                f"{self.base_url}/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": settings.LLM_ANTHROPIC_VERSION,
                    "content-type": "application/json",
                },
                json=body,
                timeout=settings.LLM_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise LLMError(f"network dikkat: {exc.__class__.__name__}") from exc
        if response.status_code >= 400:
            raise LLMError(f"provider ne {response.status_code} diya: {response.text[:200]}")

        try:
            data = response.json()
            text = "".join(b.get("text", "") for b in data["content"] if b.get("type") == "text")
        except (ValueError, KeyError, TypeError) as exc:
            raise LLMError("provider ka jawab samajh nahi aaya") from exc
        usage = data.get("usage") or {}
        return LLMResult(
            text=text,
            input_tokens=int(usage.get("input_tokens", 0)),
            output_tokens=int(usage.get("output_tokens", 0)),
            model=self.model,
        )
