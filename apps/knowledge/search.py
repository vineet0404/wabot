"""Sawal ke liye sabse kaam ke chunks dhoondhta hai: embedding se, nahi to keyword se."""

import logging
import math
import re

from django.conf import settings

from .embeddings import EmbeddingError, embed_texts, is_enabled
from .models import KnowledgeChunk

logger = logging.getLogger(__name__)

STOPWORDS = {
    "kya", "hai", "hain", "ka", "ki", "ke", "ko", "me", "mein", "se", "aur", "or", "the", "is",
    "are", "a", "an", "of", "to", "in", "for", "and", "kitna", "kitni", "kitne", "hoga", "hota",
    "mujhe", "aap", "main", "hum", "kar", "karo", "kab", "kaise", "please", "plz", "bhai",
}  # fmt: skip


def tokens(text: str) -> set[str]:
    words = [w for w in re.findall(r"\w+", (text or "").lower()) if len(w) > 2]
    words = [w for w in words if w not in STOPWORDS]
    # 4 akshar ka prefix bhi: Hinglish spelling ka thoda farak (timing/timings) chal jaye
    return set(words) | {w[:4] for w in words if len(w) > 4}


def keyword_score(query_tokens: set[str], chunk_text: str) -> float:
    if not query_tokens:
        return 0.0
    common = query_tokens & tokens(chunk_text)
    return len(common) / math.sqrt(len(query_tokens))


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def search(tenant, query: str, k: int | None = None) -> list[str]:
    """Is business ke top-k chunks (text) lautata hai. Kuch na mile to khali list."""
    k = k or settings.KB_TOP_K
    chunks = list(
        KnowledgeChunk.objects.filter(tenant=tenant, doc__is_active=True).select_related("doc")
    )
    if not chunks or not (query or "").strip():
        return []

    scored: list[tuple[float, KnowledgeChunk]] = []
    use_vectors = False
    if is_enabled() and any(c.embedding for c in chunks):
        try:
            query_vec = embed_texts([query])[0]
            use_vectors = True
        except EmbeddingError as exc:
            logger.warning("query embedding fail, keyword search par ja rahe hain: %s", exc)

    if use_vectors:
        for chunk in chunks:
            if chunk.embedding and chunk.embed_model == settings.EMBED_MODEL:
                score = cosine(query_vec, chunk.embedding)
                if score >= settings.KB_MIN_SCORE:
                    scored.append((score, chunk))
    else:
        query_tokens = tokens(query)
        for chunk in chunks:
            score = keyword_score(query_tokens, f"{chunk.doc.title} {chunk.text}")
            if score > 0:
                scored.append((score, chunk))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [f"[{c.doc.title}]\n{c.text}" for _, c in scored[:k]]
