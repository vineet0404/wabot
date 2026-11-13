import pytest

from apps.ai.prompt import build_messages, build_system_prompt
from apps.ai.providers.base import LLMError, LLMProvider, LLMResult
from apps.ai.service import (
    FALLBACK_BUDGET,
    FALLBACK_ERROR,
    FALLBACK_HANDOVER,
    FALLBACK_UNKNOWN,
    generate_reply,
)
from apps.ai.usage import tokens_used_today
from apps.core.models import Conversation, Customer, LLMUsage, Message, Tenant
from apps.whatsapp.tasks import handle_inbound_message


class Scripted(LLMProvider):
    def __init__(self, text="", error=None, tokens=(10, 5)):
        self.text, self.error, self.tokens = text, error, tokens
        self.calls = []

    def complete(self, system, messages, max_tokens):
        self.calls.append((system, messages))
        if self.error:
            raise self.error
        return LLMResult(self.text, *self.tokens)


@pytest.fixture
def tenant(db):
    return Tenant.objects.create(
        name="Sai Clinic",
        wa_phone_number_id="1",
        business_info="Timing: 10 se 7. Fees: Rs 500.",
    )


@pytest.fixture
def conversation(tenant):
    customer = Customer.objects.create(tenant=tenant, phone="919800000001")
    return Conversation.objects.create(tenant=tenant, customer=customer)


def inbound(conversation, body, wa_id):
    return Message.objects.create(
        tenant=conversation.tenant,
        conversation=conversation,
        direction="in",
        body=body,
        wa_message_id=wa_id,
    )


def test_normal_answer_passes_through_and_records_usage(conversation):
    msg = inbound(conversation, "Timing kya hai?", "w1")
    provider = Scripted("Hamari timing subah 10 se shaam 7 baje hai.")
    reply = generate_reply(msg, provider)
    assert reply.text.startswith("Hamari timing")
    assert reply.flag == ""
    usage = LLMUsage.objects.get(tenant=conversation.tenant)
    assert (usage.calls, usage.input_tokens, usage.output_tokens) == (1, 10, 5)


def test_unknown_marker_gives_safe_fallback_not_model_text(conversation):
    msg = inbound(conversation, "MRI hota hai?", "w1")
    reply = generate_reply(msg, Scripted("[[UNKNOWN]] Haan MRI Rs 5000 me hota hai"))
    assert (reply.text, reply.flag) == (FALLBACK_UNKNOWN, "unknown")


def test_handover_marker(conversation):
    msg = inbound(conversation, "Doctor se baat karni hai", "w1")
    reply = generate_reply(msg, Scripted("[[HANDOVER]]"))
    assert (reply.text, reply.flag) == (FALLBACK_HANDOVER, "handover")


def test_provider_error_and_empty_reply_give_fallback(conversation):
    msg = inbound(conversation, "Hi", "w1")
    assert generate_reply(msg, Scripted(error=LLMError("down"))).text == FALLBACK_ERROR
    assert generate_reply(msg, Scripted("   ")).flag == "error"


def test_daily_budget_blocks_calls(conversation, settings):
    settings.LLM_DAILY_TOKEN_BUDGET = 20
    msg = inbound(conversation, "Hi", "w1")
    provider = Scripted("ok", tokens=(15, 10))
    assert generate_reply(msg, provider).flag == ""
    assert tokens_used_today(conversation.tenant) == 25
    blocked = generate_reply(msg, provider)
    assert (blocked.text, blocked.flag) == (FALLBACK_BUDGET, "budget")
    assert len(provider.calls) == 1


def test_budget_zero_means_unlimited(conversation, settings):
    settings.LLM_DAILY_TOKEN_BUDGET = 0
    msg = inbound(conversation, "Hi", "w1")
    for _ in range(3):
        assert generate_reply(msg, Scripted("ok", tokens=(10**6, 10**6))).flag == ""


def test_system_prompt_has_business_info_and_rules(tenant):
    prompt = build_system_prompt(tenant)
    assert "Sai Clinic" in prompt
    assert "Timing: 10 se 7" in prompt
    assert "[[UNKNOWN]]" in prompt and "[[HANDOVER]]" in prompt
    assert "same language and script" in prompt
    tenant.business_info = ""
    assert "no information provided yet" in build_system_prompt(tenant)


def test_history_merges_roles_starts_with_user_and_trims(conversation, settings):
    settings.LLM_HISTORY_MESSAGES = 10
    Message.objects.create(
        tenant=conversation.tenant, conversation=conversation, direction="out", body="Welcome"
    )
    inbound(conversation, "Hi", "w1")
    inbound(conversation, "Timing?", "w2")
    last = inbound(conversation, "x" * 5000, "w3")
    turns = build_messages(last)
    assert turns[0]["role"] == "user"
    assert [t["role"] for t in turns] == ["user"]
    assert turns[0]["content"].startswith("Hi\nTiming?\n")
    assert len(turns[0]["content"]) < 1100


def test_history_limit_and_alternation(conversation, settings):
    settings.LLM_HISTORY_MESSAGES = 3
    inbound(conversation, "a", "w1")
    Message.objects.create(
        tenant=conversation.tenant, conversation=conversation, direction="out", body="b"
    )
    inbound(conversation, "c", "w3")
    Message.objects.create(
        tenant=conversation.tenant, conversation=conversation, direction="out", body="d"
    )
    last = inbound(conversation, "e", "w5")
    turns = build_messages(last)
    assert turns == [
        {"role": "user", "content": "c"},
        {"role": "assistant", "content": "d"},
        {"role": "user", "content": "e"},
    ]


def test_task_sets_human_state_on_handover_and_is_idempotent(conversation, monkeypatch):
    monkeypatch.setattr(
        "apps.whatsapp.tasks.generate_reply", lambda m: generate_reply(m, Scripted("[[HANDOVER]]"))
    )
    msg = inbound(conversation, "Mujhe insaan se baat karni hai", "w1")
    handle_inbound_message(msg.pk)
    handle_inbound_message(msg.pk)  # dobara chalane par dusra jawab nahi
    conversation.refresh_from_db()
    assert conversation.state == Conversation.State.HUMAN
    replies = Message.objects.filter(direction="out")
    assert replies.count() == 1
    assert replies[0].flag == "handover"
    assert replies[0].reply_to == msg


def test_task_unknown_keeps_bot_on(conversation, monkeypatch):
    monkeypatch.setattr(
        "apps.whatsapp.tasks.generate_reply", lambda m: generate_reply(m, Scripted("[[UNKNOWN]]"))
    )
    msg = inbound(conversation, "MRI?", "w1")
    handle_inbound_message(msg.pk)
    conversation.refresh_from_db()
    assert conversation.state == Conversation.State.BOT
    assert Message.objects.get(direction="out").flag == "unknown"


def test_non_text_gets_canned_reply_without_calling_ai(conversation, monkeypatch):
    def boom(m):
        raise AssertionError("AI nahi bulana chahiye")

    monkeypatch.setattr("apps.whatsapp.tasks.generate_reply", boom)
    msg = Message.objects.create(
        tenant=conversation.tenant,
        conversation=conversation,
        direction="in",
        type="image",
        wa_message_id="w9",
    )
    handle_inbound_message(msg.pk)
    assert "sirf text" in Message.objects.get(direction="out").body


def test_ai_eval_and_bootstrap_run_with_fake_provider(db, capsys):
    from django.core.management import call_command

    call_command("bootstrap_dev")
    assert "Timing" in Tenant.objects.get().business_info
    call_command("ai_eval", "--question", "Timing kya hai?")
    out = capsys.readouterr().out
    assert "Provider: fake" in out
    assert "Aapne likha" in out


def test_check_llm_with_fake_and_with_broken_provider(settings, capsys):
    from django.core.management import call_command

    call_command("check_llm")
    assert "[OK]" in capsys.readouterr().out
    settings.LLM_PROVIDER = "openai_compatible"
    settings.LLM_BASE_URL = ""
    call_command("check_llm")
    assert "[FIX]" in capsys.readouterr().out


def test_export_training_data_requires_consent_and_masks_numbers(conversation, tmp_path):
    import json

    from django.core.management import call_command
    from django.core.management.base import CommandError

    tenant = conversation.tenant
    out = tmp_path / "x.jsonl"
    with pytest.raises(CommandError):
        call_command("export_training_data", tenant=tenant.pk, out=str(out))

    msg = inbound(conversation, "Mera number 98765 43210 hai, MRI hota hai?", "w1")
    Message.objects.create(
        tenant=tenant,
        conversation=conversation,
        direction="out",
        body="Is bare me mujhe pakka pata nahi...",
        flag="unknown",
        reply_to=msg,
    )
    call_command("export_training_data", tenant=tenant.pk, out=str(out), i_have_consent=True)
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["messages"][-1]["content"] == "[[UNKNOWN]]"
    user_text = rows[0]["messages"][1]["content"]
    assert "98765" not in user_text and "[NUMBER]" in user_text


class Sequence(LLMProvider):
    def __init__(self, *texts):
        self.texts, self.systems = list(texts), []

    def complete(self, system, messages, max_tokens):
        self.systems.append(system)
        return LLMResult(self.texts.pop(0), 10, 5)


def test_wrong_script_reply_is_retried_once(conversation):
    msg = inbound(conversation, "clinic ki timing kya hai", "ws1")
    provider = Sequence("क्लिनिक सुबह 10 बजे खुलता है", "Clinic subah 10 baje khulta hai.")
    reply = generate_reply(msg, provider)
    assert reply.text == "Clinic subah 10 baje khulta hai."
    assert len(provider.systems) == 2 and "Roman letters" in provider.systems[1]


def test_script_retry_failing_keeps_first_reply_and_counts_tokens(conversation):
    msg = inbound(conversation, "timing kya hai", "ws2")
    provider = Sequence("सुबह 10 बजे", "फिर से देवनागरी में")
    assert generate_reply(msg, provider).text == "सुबह 10 बजे"
    assert tokens_used_today(conversation.tenant) == 30  # 2 calls x 15


def test_matching_script_does_not_retry(conversation):
    provider = Sequence("Timing 10 se 7 hai.")
    generate_reply(inbound(conversation, "timing kya hai", "ws3"), provider)
    assert len(provider.systems) == 1
    # Devanagari customer ko Devanagari jawab: theek
    provider = Sequence("सुबह 10 बजे")
    generate_reply(inbound(conversation, "समय क्या है", "ws4"), provider)
    assert len(provider.systems) == 1
    # Bahut chhota message: lipi ka sawal nahi
    provider = Sequence("ठीक है")
    generate_reply(inbound(conversation, "ok", "ws5"), provider)
    assert len(provider.systems) == 1


def test_script_retry_not_done_for_markers(conversation):
    provider = Sequence("[[HANDOVER]]")
    reply = generate_reply(inbound(conversation, "manager se baat karao", "ws6"), provider)
    assert reply.flag == "handover" and len(provider.systems) == 1


def test_script_helper_cases():
    from apps.ai.script import script_fix_instruction as fix

    assert fix("timing kya hai", "सुबह 10 बजे") and "Roman" in fix("timing kya hai", "सुबह")
    assert "Devanagari" in fix("समय क्या है", "10 baje")
    assert fix("timing kya hai", "10 baje khulte hain") is None
    assert fix("ok", "ठीक है") is None
