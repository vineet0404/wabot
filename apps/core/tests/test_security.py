import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import Client

from apps.core.models import Tenant
from apps.whatsapp.views import BAD_SIGNATURE_LIMIT

LOGIN = "/admin/login/"


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def staff(db):
    return get_user_model().objects.create_superuser("owner", "o@example.com", "S3cure-Pass-123")


def test_token_is_encrypted_in_database_but_readable_in_code(db):
    tenant = Tenant.objects.create(
        name="T", wa_phone_number_id="1", wa_access_token="EAAG-secret-token"
    )
    with connection.cursor() as cursor:
        cursor.execute("SELECT wa_access_token FROM core_tenant WHERE id = %s", [tenant.pk])
        raw = cursor.fetchone()[0]
    assert raw.startswith("enc::")
    assert "EAAG-secret-token" not in raw
    assert Tenant.objects.get(pk=tenant.pk).wa_access_token == "EAAG-secret-token"


def test_old_plain_text_token_still_readable(db):
    tenant = Tenant.objects.create(name="T", wa_phone_number_id="1")
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE core_tenant SET wa_access_token = 'plain-old' WHERE id = %s", [tenant.pk]
        )
    assert Tenant.objects.get(pk=tenant.pk).wa_access_token == "plain-old"


def test_admin_hides_saved_token_and_keeps_it_when_blank(staff):
    tenant = Tenant.objects.create(
        name="T", wa_phone_number_id="1", wa_access_token="EAAG-secret-token"
    )
    client = Client()
    client.force_login(staff)
    page = client.get(f"/admin/core/tenant/{tenant.pk}/change/")
    assert page.status_code == 200
    assert b"EAAG-secret-token" not in page.content

    client.post(
        f"/admin/core/tenant/{tenant.pk}/change/",
        {
            "name": "T renamed",
            "business_type": "clinic",
            "wa_phone_number_id": "1",
            "wa_access_token": "",
            "timezone": "Asia/Kolkata",
            "language": "hinglish",
            "slot_minutes": "30",
            "reminder_hours_before": "3",
            "template_lang": "en",
            "is_active": "on",
        },
    )
    tenant.refresh_from_db()
    assert tenant.name == "T renamed"
    assert tenant.wa_access_token == "EAAG-secret-token"


def test_admin_login_locks_after_repeated_failures(staff):
    client = Client()
    for _ in range(5):
        response = client.post(LOGIN, {"username": "owner", "password": "galat"})
        assert response.status_code == 200
    # Ab sahi password se bhi roka jayega
    response = client.post(LOGIN, {"username": "owner", "password": "S3cure-Pass-123"})
    assert response.status_code == 429


def test_successful_login_resets_counter(staff):
    client = Client()
    for _ in range(3):
        client.post(LOGIN, {"username": "owner", "password": "galat"})
    response = client.post(LOGIN, {"username": "owner", "password": "S3cure-Pass-123"})
    assert response.status_code == 302
    for _ in range(3):
        client.post(LOGIN, {"username": "owner", "password": "galat"})
    response = client.post(LOGIN, {"username": "owner", "password": "S3cure-Pass-123"})
    assert response.status_code == 302


def test_webhook_blocks_ip_after_many_bad_signatures(client, db):
    for _ in range(BAD_SIGNATURE_LIMIT):
        response = client.post(
            "/webhooks/whatsapp/",
            data=b"{}",
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256="sha256=bad",
        )
        assert response.status_code == 401
    response = client.post(
        "/webhooks/whatsapp/",
        data=b"{}",
        content_type="application/json",
        HTTP_X_HUB_SIGNATURE_256="sha256=bad",
    )
    assert response.status_code == 429


def test_webhook_rejects_huge_body(client, db):
    response = client.post(
        "/webhooks/whatsapp/",
        data=b"x" * 1_100_000,
        content_type="application/json",
        HTTP_X_HUB_SIGNATURE_256="sha256=bad",
    )
    assert response.status_code == 400


def test_security_headers_present(client):
    response = client.get("/health/")
    assert response["X-Frame-Options"] == "DENY"
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["Referrer-Policy"] == "same-origin"


def test_weak_admin_password_is_rejected():
    from django.contrib.auth.password_validation import validate_password
    from django.core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        validate_password("12345678")
