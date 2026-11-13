from django.core.management import call_command

from apps.core.models import Message, Tenant


def test_bootstrap_dev_is_idempotent_and_simulator_works(db):
    call_command("bootstrap_dev")
    call_command("bootstrap_dev")
    assert Tenant.objects.count() == 1
    call_command("simulate_message", "Timing kya hai?")
    assert Message.objects.filter(direction="in").count() == 1
    assert Message.objects.filter(direction="out", body="Aapne likha: Timing kya hai?").count() == 1


def test_check_setup_reports_go_live_items(db):
    from io import StringIO

    call_command("bootstrap_dev")
    out = StringIO()
    call_command("check_setup", stdout=out)
    text = out.getvalue()
    assert "Go-live checks" in text
    assert "[FIX]  LLM_PROVIDER asli hai" in text  # tests me provider 'fake' hai
    assert "inbox ke liye members" in text
