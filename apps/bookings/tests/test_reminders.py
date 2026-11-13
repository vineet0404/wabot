from datetime import datetime, timedelta
from io import StringIO
from zoneinfo import ZoneInfo

import pytest
from django.core import mail
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from apps.bookings import reminders
from apps.bookings.models import Booking
from apps.core.models import Conversation, Customer, Message, Tenant
from apps.whatsapp import client
from apps.whatsapp.client import WhatsAppError

IST = ZoneInfo("Asia/Kolkata")
NOON = datetime(2026, 11, 10, 12, 0, tzinfo=IST)  # quiet hours ke bahar


@pytest.fixture
def tenant(db):
    return Tenant.objects.create(
        name="Sai Clinic", wa_phone_number_id="1", wa_access_token="tok", reminder_hours_before=3
    )


@pytest.fixture
def conv(tenant):
    customer = Customer.objects.create(tenant=tenant, phone="919800001234", name="Ravi")
    return Conversation.objects.create(
        tenant=tenant,
        customer=customer,
        window_expires_at=timezone.now() + timedelta(hours=5),
    )


def booking(conv, starts_at, status="confirmed"):
    return Booking.objects.create(
        tenant=conv.tenant,
        customer=conv.customer,
        conversation=conv,
        starts_at=starts_at,
        status=status,
    )


@pytest.fixture
def sent(monkeypatch):
    log = []
    monkeypatch.setattr(
        reminders, "send_text", lambda t, to, body: log.append(("text", body)) or "w.1"
    )
    monkeypatch.setattr(
        reminders,
        "send_template",
        lambda t, to, name, params: log.append(("template", name, params)) or "w.2",
    )
    return log


def test_sends_once_inside_window(conv, sent):
    b = booking(conv, NOON + timedelta(hours=2))
    assert reminders.send_due_reminders(NOON)["sent"] == 1
    assert sent[0][0] == "text" and "yaad" in sent[0][1] and "Ravi" in sent[0][1]
    b.refresh_from_db()
    assert b.reminder_sent_at and b.reminder_result == "sent"
    assert Message.objects.filter(conversation=conv, flag="reminder").count() == 1
    # Dobara chalane par koi reminder nahi
    assert reminders.send_due_reminders(NOON)["sent"] == 0
    assert len(sent) == 1


def test_not_due_or_not_confirmed_are_ignored(conv, sent):
    booking(conv, NOON + timedelta(hours=5))  # abhi door hai
    booking(conv, NOON + timedelta(hours=1), status="requested")
    booking(conv, NOON + timedelta(hours=1), status="rejected")
    booking(conv, NOON + timedelta(hours=1), status="cancelled")
    booking(conv, NOON - timedelta(hours=1))  # beet gaya
    assert reminders.send_due_reminders(NOON) == {"sent": 0, "skipped": 0, "failed": 0, "quiet": 0}
    assert sent == []


def test_reminders_off_or_tenant_inactive(conv, sent):
    booking(conv, NOON + timedelta(hours=1))
    conv.tenant.reminder_hours_before = 0
    conv.tenant.save()
    assert reminders.send_due_reminders(NOON)["sent"] == 0
    conv.tenant.reminder_hours_before = 3
    conv.tenant.is_active = False
    conv.tenant.save()
    assert reminders.send_due_reminders(NOON)["sent"] == 0


def test_quiet_hours_wait_and_send_later(conv, sent):
    night = datetime(2026, 11, 10, 5, 0, tzinfo=IST)
    b = booking(conv, night + timedelta(hours=2))  # subah 7 baje ka appointment
    assert reminders.send_due_reminders(night)["quiet"] == 1
    assert sent == []
    b.refresh_from_db()
    assert b.reminder_sent_at is None


def test_after_quiet_hours_sends(conv, sent):
    morning = datetime(2026, 11, 10, 8, 30, tzinfo=IST)
    booking(conv, morning + timedelta(hours=1))
    assert reminders.send_due_reminders(morning)["sent"] == 1


def test_window_closed_uses_template(conv, sent):
    conv.window_expires_at = timezone.now() - timedelta(hours=1)
    conv.save()
    conv.tenant.reminder_template = "appt_reminder"
    conv.tenant.save()
    booking(conv, NOON + timedelta(hours=2))
    assert reminders.send_due_reminders(NOON)["sent"] == 1
    kind, name, params = sent[0]
    assert (kind, name) == ("template", "appt_reminder")
    assert params[0] == "Ravi" and params[2] == "Sai Clinic"


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_window_closed_without_template_skips_and_tells_owner(conv, sent):
    conv.window_expires_at = timezone.now() - timedelta(hours=1)
    conv.save()
    conv.tenant.notify_email = "owner@example.com"
    conv.tenant.save()
    b = booking(conv, NOON + timedelta(hours=2))
    assert reminders.send_due_reminders(NOON)["skipped"] == 1
    assert sent == []
    b.refresh_from_db()
    assert b.reminder_result == "skipped"
    assert len(mail.outbox) == 1 and "reminder nahi ja saka" in mail.outbox[0].body


def test_send_failure_is_retried_next_run(conv, monkeypatch):
    calls = {"n": 0}

    def flaky(t, to, body):
        calls["n"] += 1
        if calls["n"] == 1:
            raise WhatsAppError("Meta down")
        return "w.7"

    monkeypatch.setattr(reminders, "send_text", flaky)
    b = booking(conv, NOON + timedelta(hours=2))
    assert reminders.send_due_reminders(NOON)["failed"] == 1
    b.refresh_from_db()
    assert b.reminder_sent_at is None
    assert reminders.send_due_reminders(NOON + timedelta(minutes=10))["sent"] == 1


def test_command_dry_run_and_real(conv, sent):
    out = StringIO()
    # Asli "abhi" use hota hai, isliye booking 1 ghante baad ki rakho
    booking(conv, timezone.now() + timedelta(hours=1))
    call_command("send_reminders", "--dry-run", stdout=out)
    assert "1 reminder due" in out.getvalue() and sent == []


def test_beat_schedule_points_to_real_task():
    from config.celery import app

    entry = app.conf.beat_schedule["send-due-reminders"]
    assert entry["task"] == "apps.bookings.tasks.send_due_reminders_task"
    app.loader.import_default_modules()
    assert entry["task"] in app.tasks


def test_send_template_payload(conv, monkeypatch):
    seen = {}

    class Resp:
        status_code = 200
        text = "{}"

        def json(self):
            return {"messages": [{"id": "wamid.T"}]}

    def fake_post(url, headers, json, timeout):
        seen.update(json=json)
        return Resp()

    monkeypatch.setattr(client.requests, "post", fake_post)
    wa_id = client.send_template(
        conv.tenant, "919800001234", "appt_reminder", ["Ravi", "Mon", "Sai"]
    )
    assert wa_id == "wamid.T"
    assert seen["json"]["type"] == "template"
    tpl = seen["json"]["template"]
    assert tpl["name"] == "appt_reminder" and tpl["language"] == {"code": "en"}
    assert [p["text"] for p in tpl["components"][0]["parameters"]] == ["Ravi", "Mon", "Sai"]


def test_send_template_error_and_dry_run(conv, monkeypatch):
    class Bad:
        status_code = 400
        text = "template not found"

    monkeypatch.setattr(client.requests, "post", lambda *a, **k: Bad())
    with pytest.raises(WhatsAppError):
        client.send_template(conv.tenant, "9198", "x", [])
    conv.tenant.wa_access_token = ""
    monkeypatch.setattr(
        client.requests, "post", lambda *a, **k: pytest.fail("dry-run me call nahi")
    )
    assert client.send_template(conv.tenant, "9198", "x", []) is None
