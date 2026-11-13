import pytest
from django.core.management import call_command
from django.test import override_settings

from apps.ai.prompt import build_system_prompt
from apps.ai.service import generate_reply
from apps.core.models import Conversation, Customer, Message, Tenant
from apps.knowledge import embeddings
from apps.knowledge.chunking import split_text
from apps.knowledge.models import KnowledgeChunk, KnowledgeDoc
from apps.knowledge.search import search
from apps.knowledge.service import reindex
from tests_helpers import Scripted


@pytest.fixture
def tenant(db):
    return Tenant.objects.create(
        name="Glow Salon", wa_phone_number_id="9", business_info="Open 10-8"
    )


def make_doc(tenant, title, content):
    doc = KnowledgeDoc.objects.create(tenant=tenant, title=title, content=content)
    reindex(doc)
    return doc


def test_split_text_keeps_paragraphs_and_limits_size():
    text = "Haircut Rs 300\n\nFacial Rs 800\n\n" + ("Bahut lamba vakya. " * 80)
    pieces = split_text(text, max_chars=200)
    assert all(len(p) <= 200 for p in pieces)
    assert "Haircut Rs 300" in pieces[0]
    assert split_text("") == []


def test_keyword_search_finds_right_chunk_and_tenant_isolated(tenant):
    make_doc(tenant, "Rates", "Haircut Rs 300\n\nBridal makeup Rs 8000 advance booking")
    make_doc(tenant, "Timing", "Sunday ko salon band rehta hai\n\nRoz 10 se 8 baje khula")
    other = Tenant.objects.create(name="Other", wa_phone_number_id="10")
    make_doc(other, "Rates", "Bridal makeup Rs 99999")

    hits = search(tenant, "bridal makeup ka rate kya hai")
    assert hits and "8000" in hits[0]
    assert all("99999" not in h for h in hits)
    assert search(tenant, "xyzzy qwerty") == []


def test_inactive_doc_is_ignored(tenant):
    doc = make_doc(tenant, "Old", "Purana offer 50 percent off")
    doc.is_active = False
    doc.save()
    assert search(tenant, "offer") == []


def test_prompt_includes_retrieved_chunks(tenant):
    make_doc(tenant, "Rates", "Bridal makeup Rs 8000")
    prompt = build_system_prompt(tenant, "bridal makeup price")
    assert "Bridal makeup Rs 8000" in prompt
    assert "Open 10-8" in prompt
    assert "Bridal makeup" not in build_system_prompt(tenant)


def test_generate_reply_passes_knowledge_to_provider(tenant):
    make_doc(tenant, "Rates", "Bridal makeup Rs 8000")
    customer = Customer.objects.create(tenant=tenant, phone="91")
    conv = Conversation.objects.create(tenant=tenant, customer=customer)
    msg = Message.objects.create(
        tenant=tenant,
        conversation=conv,
        direction="in",
        body="bridal makeup kitne ka hai",
        wa_message_id="w1",
    )
    provider = Scripted(text="Rs 8000 hai.")
    reply = generate_reply(msg, provider=provider)
    assert reply.text == "Rs 8000 hai."
    assert "Bridal makeup Rs 8000" in provider.calls[0][0]


def test_search_failure_does_not_break_prompt(tenant, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr("apps.knowledge.search.search", boom)
    assert "Open 10-8" in build_system_prompt(tenant, "kuch bhi")


EMBED = dict(EMBED_PROVIDER="openai_compatible", EMBED_BASE_URL="http://x/v1", EMBED_MODEL="m1")


def fake_vectors(texts):
    # "rate" wale text ek direction me, "timing" wale doosri me
    return [[1.0, 0.0] if "Rs" in t or "rate" in t else [0.0, 1.0] for t in texts]


@override_settings(**EMBED)
def test_vector_search_used_when_embeddings_enabled(tenant, monkeypatch):
    monkeypatch.setattr("apps.knowledge.service.embed_texts", fake_vectors)
    monkeypatch.setattr("apps.knowledge.search.embed_texts", fake_vectors)
    make_doc(tenant, "Rates", "Haircut Rs 300")
    make_doc(tenant, "Timing", "Roz subah khulta hai")
    assert KnowledgeChunk.objects.filter(embedding__isnull=False).count() == 2
    hits = search(tenant, "rate batao", k=1)
    assert len(hits) == 1 and "Haircut" in hits[0]


@override_settings(**EMBED)
def test_embedding_failure_falls_back_to_keywords(tenant, monkeypatch):
    def fail(texts):
        raise embeddings.EmbeddingError("down")

    monkeypatch.setattr("apps.knowledge.service.embed_texts", fail)
    monkeypatch.setattr("apps.knowledge.search.embed_texts", fail)
    make_doc(tenant, "Rates", "Haircut Rs 300")
    assert KnowledgeChunk.objects.filter(embedding__isnull=True).count() == 1
    assert search(tenant, "haircut kitne ka") != []


@override_settings(**EMBED)
def test_embed_texts_parses_openai_style_response(monkeypatch):
    class Resp:
        status_code = 200

        def json(self):
            return {"data": [{"index": 1, "embedding": [0, 1]}, {"index": 0, "embedding": [1, 0]}]}

    monkeypatch.setattr(embeddings.requests, "post", lambda *a, **k: Resp())
    assert embeddings.embed_texts(["a", "b"]) == [[1.0, 0.0], [0.0, 1.0]]


def test_kb_import_command(tenant, tmp_path):
    f = tmp_path / "menu.txt"
    f.write_text("Paneer tikka Rs 220\n\nDal makhani Rs 180", encoding="utf-8")
    call_command("kb_import", str(f), "--tenant", str(tenant.pk))
    call_command("kb_import", str(f), "--tenant", str(tenant.pk))  # dobara: duplicate nahi
    assert KnowledgeDoc.objects.filter(tenant=tenant).count() == 1
    assert search(tenant, "paneer tikka") != []
