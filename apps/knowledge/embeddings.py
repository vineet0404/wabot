"""Text ko numbers (embedding) me badalta hai. Provider badla ja sakta hai, jaise LLM ka.

EMBED_PROVIDER: none (default, sirf keyword search) | openai | ollama | local | gemini | together |
openai_compatible. Sab "OpenAI jaise" /embeddings API se baat karte hain.
"""

import logging

import requests
from django.conf import settings

from apps.ai.providers.openai_compatible import PRESET_URLS

logger = logging.getLogger(__name__)


class EmbeddingError(Exception):
    pass


def is_enabled() -> bool:
    return (settings.EMBED_PROVIDER or "none").strip().lower() not in ("", "none")


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    if not is_enabled():
        raise EmbeddingError("EMBED_PROVIDER set nahi hai")
    preset = settings.EMBED_PROVIDER.strip().lower()
    base_url = (settings.EMBED_BASE_URL or PRESET_URLS.get(preset, "")).rstrip("/")
    if not base_url or not settings.EMBED_MODEL:
        raise EmbeddingError("EMBED_BASE_URL (ya preset) aur EMBED_MODEL set karo")
    headers = {"Content-Type": "application/json"}
    if settings.EMBED_API_KEY:
        headers["Authorization"] = f"Bearer {settings.EMBED_API_KEY}"
    try:
        response = requests.post(
            f"{base_url}/embeddings",
            headers=headers,
            json={"model": settings.EMBED_MODEL, "input": texts},
            timeout=settings.EMBED_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise EmbeddingError(f"network dikkat: {exc.__class__.__name__}") from exc
    if response.status_code >= 400:
        raise EmbeddingError(f"provider ne {response.status_code} diya: {response.text[:200]}")
    try:
        rows = sorted(response.json()["data"], key=lambda r: r.get("index", 0))
        vectors = [[float(x) for x in r["embedding"]] for r in rows]
    except (ValueError, KeyError, TypeError) as exc:
        raise EmbeddingError("provider ka jawab samajh nahi aaya") from exc
    if len(vectors) != len(texts):
        raise EmbeddingError("embeddings ki ginti texts se alag hai")
    return vectors
