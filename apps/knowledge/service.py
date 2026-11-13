import logging

from django.conf import settings
from django.db import transaction

from .chunking import split_text
from .embeddings import EmbeddingError, embed_texts, is_enabled
from .models import KnowledgeChunk, KnowledgeDoc

logger = logging.getLogger(__name__)


def reindex(doc: KnowledgeDoc) -> int:
    """Doc ke chunks (aur chalu ho to embeddings) dobara banata hai. Chunks ki ginti deta hai."""
    pieces = split_text(doc.content)
    vectors: list[list[float]] = []
    model_name = ""
    if is_enabled() and pieces:
        try:
            vectors = embed_texts(pieces)
            model_name = settings.EMBED_MODEL
        except EmbeddingError as exc:
            logger.warning("embedding nahi bani, keyword search chalega: %s", exc)

    with transaction.atomic():
        doc.chunks.all().delete()
        KnowledgeChunk.objects.bulk_create(
            KnowledgeChunk(
                tenant=doc.tenant,
                doc=doc,
                position=i,
                text=text,
                embedding=vectors[i] if vectors else None,
                embed_model=model_name,
            )
            for i, text in enumerate(pieces)
        )
    return len(pieces)
