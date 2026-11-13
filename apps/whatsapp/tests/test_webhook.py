import hashlib
import hmac
import json

import pytest
from django.conf import settings

from apps.core.models import Conversation, Message, Tenant
from apps.whatsapp.signature import verify_signature

URL = "/webhooks/whatsapp/"
PHONE_NUMBER_ID = "1234567890"


def make_payload(text="Namaste", wa_id="wamid.AAA", sender="919800000001", phone_number_id=None):
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA_ID",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"phone_number_id": phone_number_id or PHONE_NUMBER_ID},
                            "contacts": [{"wa_id": sender, "profile": {"name": "Priya"}}],
                            "messages": [
                                {
                                    "from": sender,
                                    "id": wa_id,
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


def post(client, payload, secret=None):
    body = json.dumps(payload).encode()
    digest = hmac.new((secret or settings.META_APP_SECRET).encode(), body, hashlib.sha256)
    return client.post(
        URL,
        data=body,
        content_type="application/json",
        HTTP_X_HUB_SIGNATURE_256="sha256=" + digest.hexdigest(),
    )


@pytest.fixture
def tenant(db):
    return Tenant.objects.create(name="Sai Dental Clinic", wa_phone_number_id=PHONE_NUMBER_ID)


def test_signature_helper():
    body = b'{"a": 1}'
    good = "sha256=" + hmac.new(b"s", body, hashlib.sha256).hexdigest()
    assert verify_signature("s", body, good)
    assert not verify_signature("s", body, "sha256=deadbeef")
    assert not verify_signature("s", body, None)
    assert not verify_signature("", body, good)


def test_verify_ok(client):
    response = client.get(
        URL,
        {
            "hub.mode": "subscribe",
            "hub.verify_token": settings.META_VERIFY_TOKEN,
            "hub.challenge": "12345",
        },
    )
    assert response.status_code == 200
    assert response.content == b"12345"


def test_verify_wrong_token(client):
    response = client.get(
        URL, {"hub.mode": "subscribe", "hub.verify_token": "galat", "hub.challenge": "1"}
    )
    assert response.status_code == 403


def test_post_bad_signature_is_rejected(client, tenant):
    response = post(client, make_payload(), secret="galat-secret")
    assert response.status_code == 401
    assert Message.objects.count() == 0


def test_post_saves_message_and_echoes(client, tenant):
    response = post(client, make_payload(text="Timing kya hai?"))
    assert response.status_code == 200

    inbound = Message.objects.get(direction=Message.Direction.IN)
    assert inbound.body == "Timing kya hai?"
    assert inbound.tenant == tenant
    assert inbound.conversation.customer.name == "Priya"
    assert inbound.conversation.window_expires_at is not None

    outbound = Message.objects.get(direction=Message.Direction.OUT)
    assert outbound.body == "Aapne likha: Timing kya hai?"


def test_duplicate_message_is_processed_once(client, tenant):
    payload = make_payload(wa_id="wamid.SAME")
    post(client, payload)
    post(client, payload)
    assert Message.objects.filter(direction=Message.Direction.IN).count() == 1
    assert Message.objects.filter(direction=Message.Direction.OUT).count() == 1


def test_unknown_business_number_returns_200_and_saves_nothing(client, tenant):
    response = post(client, make_payload(phone_number_id="999"))
    assert response.status_code == 200
    assert Message.objects.count() == 0


def test_bot_is_silent_when_owner_has_taken_over(client, tenant):
    post(client, make_payload(wa_id="wamid.ONE"))
    Conversation.objects.update(state=Conversation.State.HUMAN)
    post(client, make_payload(wa_id="wamid.TWO", text="Owner se baat karni hai"))
    assert Message.objects.filter(direction=Message.Direction.IN).count() == 2
    assert Message.objects.filter(direction=Message.Direction.OUT).count() == 1


def test_tenants_do_not_mix(client, tenant):
    other = Tenant.objects.create(name="Glow Salon", wa_phone_number_id="555")
    post(client, make_payload(wa_id="wamid.A", phone_number_id=PHONE_NUMBER_ID))
    post(client, make_payload(wa_id="wamid.B", phone_number_id="555"))
    assert Message.objects.filter(tenant=tenant, direction=Message.Direction.IN).count() == 1
    assert Message.objects.filter(tenant=other, direction=Message.Direction.IN).count() == 1


def test_health(client):
    response = client.get("/health/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
