from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.core.management.commands.latency_report import percentile
from apps.core.models import Conversation, Customer, Message, Tenant
from apps.whatsapp import client
from apps.whatsapp.tasks import handle_inbound_message


@pytest.fixture
def tenant(db):
    return Tenant.objects.create(name="Sai", wa_phone_number_id="55", wa_access_token="tok")


@pytest.fixture
def inbound(tenant):
    customer = Customer.objects.create(tenant=tenant, phone="919800000001")
    conv = Conversation.objects.create(tenant=tenant, customer=customer)
    return Message.objects.create(
        tenant=tenant,
        conversation=conv,
        direction="in",
        body="Timing kya hai?",
        wa_message_id="wamid.IN1",
    )


class FakeResponse:
    def __init__(self, status=200, text="{}"):
        self.status_code = status
        self.text = text

    def json(self):
        return {"messages": [{"id": "wamid.OUT"}]}


def test_mark_read_sends_read_and_typing(tenant, monkeypatch):
    seen = {}

    def fake_post(url, headers, json, timeout):
        seen.update(url=url, headers=headers, json=json)
        return FakeResponse()

    monkeypatch.setattr(client.requests, "post", fake_post)
    client.mark_read(tenant, "wamid.IN1")
    assert seen["url"].endswith("/55/messages")
    assert seen["json"] == {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": "wamid.IN1",
        "typing_indicator": {"type": "text"},
    }
    assert seen["headers"]["Authorization"] == "Bearer tok"


def test_mark_read_without_token_does_nothing(db, monkeypatch):
    monkeypatch.setattr(client.requests, "post", lambda *a, **k: pytest.fail("call nahi hona tha"))
    client.mark_read(Tenant(name="x", wa_phone_number_id="1"), "wamid.1")


def test_mark_read_error_raises(tenant, monkeypatch):
    monkeypatch.setattr(client.requests, "post", lambda *a, **k: FakeResponse(400, "bad"))
    with pytest.raises(client.WhatsAppError):
        client.mark_read(tenant, "wamid.IN1")


def test_task_marks_read_then_replies_and_records_latency(inbound, monkeypatch):
    order = []
    monkeypatch.setattr("apps.whatsapp.tasks.mark_read", lambda t, mid: order.append("read"))
    monkeypatch.setattr(
        "apps.whatsapp.tasks.send_text", lambda t, to, body: order.append("send") or "wamid.OUT"
    )
    handle_inbound_message(inbound.pk)
    assert order == ["read", "send"]
    out = Message.objects.get(reply_to=inbound)
    assert out.total_ms is not None and out.total_ms >= 0
    assert out.llm_ms is not None


def test_read_receipt_failure_never_blocks_reply(inbound, monkeypatch):
    def boom(t, mid):
        raise client.WhatsAppError("Meta down")

    monkeypatch.setattr("apps.whatsapp.tasks.mark_read", boom)
    monkeypatch.setattr("apps.whatsapp.tasks.send_text", lambda *a: "wamid.OUT")
    handle_inbound_message(inbound.pk)
    assert Message.objects.filter(reply_to=inbound).exists()


def test_percentile():
    assert percentile([], 95) == 0
    assert percentile([5], 50) == 5
    values = list(range(1, 101))
    assert percentile(values, 50) == 50
    assert percentile(values, 95) == 95


def test_latency_report(tenant, inbound):
    conv = inbound.conversation
    for total in (2000, 3000, 4000, 15000):
        Message.objects.create(
            tenant=tenant,
            conversation=conv,
            direction="out",
            body="ok",
            total_ms=total,
            llm_ms=total - 500,
        )
    old = Message.objects.create(
        tenant=tenant, conversation=conv, direction="out", body="purana", total_ms=99000
    )
    Message.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=30))
    out = StringIO()
    call_command("latency_report", stdout=out)
    text = out.getvalue()
    assert "4 jawab" in text
    assert "10 second se zyada: 1/4" in text
    assert "[FIX] p95" in text


def test_latency_report_empty(db):
    out = StringIO()
    call_command("latency_report", stdout=out)
    assert "koi jawab record nahi" in out.getvalue()
