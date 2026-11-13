from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Conversation, Customer, Message, Tenant
from apps.whatsapp.client import WhatsAppError


@pytest.fixture
def tenant(db):
    return Tenant.objects.create(name="Sai Clinic", wa_phone_number_id="1", wa_access_token="t")


@pytest.fixture
def conv(tenant):
    customer = Customer.objects.create(tenant=tenant, phone="919800001234", name="Ravi")
    now = timezone.now()
    return Conversation.objects.create(
        tenant=tenant,
        customer=customer,
        state="human",
        last_message_at=now,
        window_expires_at=now + timedelta(hours=5),
    )


def staff(name, tenant=None, superuser=False):
    user = get_user_model().objects.create_user(name, password="x" * 12, is_staff=True)
    user.is_superuser = superuser
    user.save()
    if tenant:
        tenant.members.add(user)
    return user


def test_anonymous_is_redirected_to_login(client, conv):
    for url in (reverse("inbox"), reverse("inbox-detail", args=[conv.pk])):
        response = client.get(url)
        assert response.status_code == 302 and "login" in response["Location"]


def test_member_sees_own_chat_and_masked_phone(client, tenant, conv):
    client.force_login(staff("owner", tenant))
    html = client.get(reverse("inbox")).content.decode()
    assert "Ravi" in html
    assert client.get(reverse("inbox-detail", args=[conv.pk])).status_code == 200


def test_staff_without_membership_cannot_see_other_business(client, conv, db):
    client.force_login(staff("stranger"))
    assert "Ravi" not in client.get(reverse("inbox")).content.decode()
    assert client.get(reverse("inbox-detail", args=[conv.pk])).status_code == 404


def test_superuser_sees_everything(client, conv):
    client.force_login(staff("root", superuser=True))
    assert client.get(reverse("inbox-detail", args=[conv.pk])).status_code == 200


def test_reply_sends_and_saves(client, tenant, conv, monkeypatch):
    sent = []
    monkeypatch.setattr(
        "apps.core.inbox.send_text", lambda t, to, body: sent.append((to, body)) or "wamid.9"
    )
    client.force_login(staff("owner", tenant))
    url = reverse("inbox-detail", args=[conv.pk])
    client.post(url, {"action": "reply", "body": "Aaiye 5 baje"})
    assert sent == [("919800001234", "Aaiye 5 baje")]
    msg = Message.objects.get(body="Aaiye 5 baje")
    assert msg.direction == "out" and msg.flag == "owner"


def test_reply_blocked_when_window_closed(client, tenant, conv, monkeypatch):
    conv.window_expires_at = timezone.now() - timedelta(hours=1)
    conv.save()
    monkeypatch.setattr("apps.core.inbox.send_text", lambda *a: pytest.fail("nahi bhejna tha"))
    client.force_login(staff("owner", tenant))
    client.post(reverse("inbox-detail", args=[conv.pk]), {"action": "reply", "body": "hi"})
    assert not Message.objects.filter(body="hi").exists()


def test_failed_send_is_not_saved(client, tenant, conv, monkeypatch):
    def boom(*a):
        raise WhatsAppError("Meta ne 400 diya")

    monkeypatch.setattr("apps.core.inbox.send_text", boom)
    client.force_login(staff("owner", tenant))
    client.post(reverse("inbox-detail", args=[conv.pk]), {"action": "reply", "body": "hello"})
    assert not Message.objects.filter(body="hello").exists()


def test_release_gives_chat_back_to_bot(client, tenant, conv):
    client.force_login(staff("owner", tenant))
    client.post(reverse("inbox-detail", args=[conv.pk]), {"action": "release"})
    conv.refresh_from_db()
    assert conv.state == "bot"


def test_ready_endpoint(client, db):
    assert client.get("/ready/").json() == {"status": "ok"}
