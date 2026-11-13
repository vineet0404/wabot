import logging
import time

import requests
from django.conf import settings

from .base import LLMError, LLMProvider, LLMResult

logger = logging.getLogger(__name__)

# Jin providers ka API "OpenAI jaisa" hota hai. URL badal sakte hain, docs se confirm karo.
PRESET_URLS = {
    "openai": "https://api.openai.com/v1",
    "groq": "https://api.groq.com/openai/v1",
    "together": "https://api.together.xyz/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
    "ollama": "http://host.docker.internal:11434/v1",  # Windows/Mac par chalta Ollama
    "local": "http://ollama:11434/v1",  # docker-compose ka ollama container
}


RETRY_STATUSES = {429, 500, 502, 503, 504}
MAX_RETRY_WAIT = 5  # second. Isse zyada ruke to customer intezaar karta rahega


def _retry_after(response, default: float) -> float:
    headers = getattr(response, "headers", None) or {}
    try:
        value = float(headers.get("retry-after", default))
    except (TypeError, ValueError):
        value = default
    return max(0.0, min(value, MAX_RETRY_WAIT))


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI, Groq, Together, OpenRouter, Gemini, Ollama, vLLM, LM Studio sab ke liye."""

    def __init__(self, preset: str = "openai_compatible"):
        self.base_url = (settings.LLM_BASE_URL or PRESET_URLS.get(preset, "")).rstrip("/")
        self.api_key = settings.LLM_API_KEY
        self.model = settings.LLM_MODEL
        if not self.base_url:
            raise LLMError(
                "LLM_BASE_URL set karo (ya LLM_PROVIDER me openai, groq, ollama jaisa naam do)."
            )
        if not self.model:
            raise LLMError("LLM_MODEL set karo (model ka naam).")

    def _post_with_retries(self, headers, body):
        """429 (rate limit), 5xx aur network gadbad par thoda ruk kar dobara koshish."""
        attempts = 1 + max(0, settings.LLM_RETRIES)
        for attempt in range(1, attempts + 1):
            last = attempt == attempts
            try:
                response = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=body,
                    timeout=settings.LLM_TIMEOUT,
                )
            except requests.RequestException as exc:
                if last:
                    raise LLMError(f"network dikkat: {exc.__class__.__name__}") from exc
                time.sleep(min(attempt, MAX_RETRY_WAIT))
                continue
            if response.status_code in RETRY_STATUSES and not last:
                wait = _retry_after(response, default=attempt)
                logger.warning("provider ne %s diya, %.1fs baad dobara", response.status_code, wait)
                time.sleep(wait)
                continue
            return response

    def complete(self, system: str, messages: list[dict], max_tokens: int) -> LLMResult:
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, *messages],
            settings.LLM_MAX_TOKENS_PARAM: max_tokens,
        }
        if settings.LLM_TEMPERATURE != "":
            body["temperature"] = float(settings.LLM_TEMPERATURE)
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        response = self._post_with_retries(headers, body)
        if response.status_code >= 400:
            raise LLMError(f"provider ne {response.status_code} diya: {response.text[:200]}")

        try:
            data = response.json()
            choice = data["choices"][0]
            text = choice["message"]["content"] or ""
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMError("provider ka jawab samajh nahi aaya") from exc
        if not text.strip():
            reason = choice.get("finish_reason")
            if reason == "length":
                raise LLMError(
                    "jawab khali: token limit me 'sochne' me hi khatam ho gaye. "
                    "LLM_MAX_OUTPUT_TOKENS badhao (jaise 1500)"
                )
            raise LLMError(f"provider ne khali jawab diya (finish_reason={reason})")
        usage = data.get("usage") or {}
        return LLMResult(
            text=text,
            input_tokens=int(usage.get("prompt_tokens", 0)),
            output_tokens=int(usage.get("completion_tokens", 0)),
            model=self.model,
        )
