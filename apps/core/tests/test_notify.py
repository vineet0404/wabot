import pytest
from django.core import mail
from django.test import override_settings

from apps.core import notify
from apps.core.models import Conversation, Customer, Message, Tenant
from apps.core.tasks import notify_owner_task
from apps.whatsapp.tasks import handle_inbound_message
from tests_helpers import Scripted


@pytest.fixture
def tenant(db):
    return Tenant.objects.create(name="Sai Clinic", wa_phone_number_id="1")


def test_no_channels_configured_is_quiet(tenant):
    assert notify.notify_owner(tenant, "hi") == []


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_email_channel(tenant):
    tenant.notify_email = "owner@example.com"
    assert notify.notify_owner(tenant, "Ravi ko zaroorat hai") == ["email"]
    assert mail.outbox[0].to == ["owner@example.com"]
    assert "Ravi" in mail.outbox[0].body


@override_settings(TELEGRAM_BOT_TOKEN="123:abc")
def test_telegram_channel_and_token_not_leaked_in_error(tenant, monkeypatch):
    tenant.notify_telegram_chat_id = "555"
    seen = {}

    class Resp:
        status_code = 200
        text = "{}"

    def fake_post(url, json, timeout):
        seen.update(url=url, json=json)
        return Resp()

    monkeypatch.setattr(notify.requests, "post", fake_post)
    assert notify.notify_owner(tenant, "hello") == ["telegram"]
    assert seen["json"] == {"chat_id": "555", "text": "hello"}

    Resp.status_code, Resp.text = 401, "unauthorized"
    with pytest.raises(notify.NotifyError) as err:
        notify.notify_owner(tenant, "hello")
    assert "123:abc" not in str(err.value)


@override_settings(
    TELEGRAM_BOT_TOKEN="123:abc", EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
)
def test_one_channel_failing_does_not_stop_the_other(tenant, monkeypatch):
    tenant.notify_telegram_chat_id = "555"
    tenant.notify_email = "o@example.com"

    def boom(*a, **k):
        raise notify.requests.ConnectionError("down")

    monkeypatch.setattr(notify.requests, "post", boom)
    assert notify.notify_owner(tenant, "x") == ["email"]


def test_task_for_missing_tenant(db):
    assert "skipped" in notify_owner_task(999, "hi")


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_handover_notifies_owner_without_customer_text(tenant, monkeypatch):
    tenant.notify_email = "owner@example.com"
    tenant.save()
    customer = Customer.objects.create(tenant=tenant, phone="919800001234", name="Ravi")
    conv = Conversation.objects.create(tenant=tenant, customer=customer)
    msg = Message.objects.create(
        tenant=tenant,
        conversation=conv,
        direction="in",
        body="mera SECRET-TEXT-123",
        wa_message_id="w1",
    )
    monkeypatch.setattr("apps.ai.service.get_provider", lambda: Scripted(text="[[HANDOVER]]"))
    monkeypatch.setattr("apps.whatsapp.tasks.send_text", lambda *a: "wamid.1")
    handle_inbound_message(msg.pk)

    assert len(mail.outbox) == 1
    body = mail.outbox[0].body
    assert "Ravi" in body and f"/inbox/{conv.pk}/" in body
    assert "SECRET-TEXT-123" not in body
    assert "9800001234" not in body  # poora number nahi


def test_notification_failure_never_blocks_handover(tenant, monkeypatch):
    customer = Customer.objects.create(tenant=tenant, phone="919800001234")
    conv = Conversation.objects.create(tenant=tenant, customer=customer)
    msg = Message.objects.create(
        tenant=tenant, conversation=conv, direction="in", body="owner se baat", wa_message_id="w2"
    )
    monkeypatch.setattr("apps.ai.service.get_provider", lambda: Scripted(text="[[HANDOVER]]"))
    monkeypatch.setattr("apps.whatsapp.tasks.send_text", lambda *a: "wamid.1")

    def boom(*a, **k):
        raise RuntimeError("redis down")

    monkeypatch.setattr("apps.core.tasks.notify_owner_task.delay", boom)
    handle_inbound_message(msg.pk)
    conv.refresh_from_db()
    assert conv.state == "human"
    assert Message.objects.filter(reply_to=msg, flag="handover").exists()


def test_notify_test_command(tenant):
    from io import StringIO

    from django.core.management import call_command

    out = StringIO()
    call_command("notify_test", stdout=out)
    assert "[FIX] Koi channel set nahi" in out.getvalue()
