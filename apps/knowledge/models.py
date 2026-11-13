from django.db import models

from apps.core.models import Tenant


class KnowledgeDoc(models.Model):
    """Business ka ek document: menu, rate list, FAQ, policy. Save par chunks ban jaate hain."""

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="knowledge_docs")
    title = models.CharField(max_length=160)
    content = models.TextField(help_text="Saada text. Paragraphs ke beech khali line rakho.")
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class KnowledgeChunk(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="knowledge_chunks")
    doc = models.ForeignKey(KnowledgeDoc, on_delete=models.CASCADE, related_name="chunks")
    position = models.PositiveIntegerField()
    text = models.TextField()
    embedding = models.JSONField(null=True, blank=True)
    embed_model = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["doc_id", "position"]

    def __str__(self):
        return f"{self.doc_id}#{self.position}"
