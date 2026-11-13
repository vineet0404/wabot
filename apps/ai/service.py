import logging
import time
from dataclasses import dataclass

from django.conf import settings

from apps.core.models import Message

from .prompt import build_messages, build_system_prompt, recent_user_text
from .prompt_template import FALLBACK_HANDOVER, FALLBACK_UNKNOWN
from .providers.base import LLMError, LLMProvider
from .providers.registry import get_provider
from .script import script_fix_instruction
from .usage import budget_exceeded, record_usage

logger = logging.getLogger(__name__)

UNKNOWN_MARKER = "[[UNKNOWN]]"
HANDOVER_MARKER = "[[HANDOVER]]"

FALLBACK_ERROR = "Abhi thodi technical dikkat hai. Hamari team jaldi aapko reply karegi."
FALLBACK_BUDGET = (
    "Aaj ke liye auto-reply ki limit poori ho gayi hai. Hamari team jaldi reply karegi."
)

MAX_REPLY_CHARS = 1500


@dataclass
class Reply:
    text: str
    flag: str = ""  # "", unknown, handover, error, budget
    llm_ms: int | None = None  # AI call me lage millisecond (AI chala ho tabhi)


def generate_reply(message: Message, provider: LLMProvider | None = None) -> Reply:
    """Customer ke message ka jawab banata hai. Kabhi exception nahi uthata, fallback deta hai."""
    tenant = message.tenant

    if budget_exceeded(tenant):
        logger.warning("tenant=%s ka daily AI budget poora", tenant.pk)
        return Reply(FALLBACK_BUDGET, "budget")

    started = time.monotonic()
    try:
        provider = provider or get_provider()
        system = build_system_prompt(tenant, recent_user_text(message))
        history = build_messages(message)
        result = provider.complete(
            system=system, messages=history, max_tokens=settings.LLM_MAX_OUTPUT_TOKENS
        )
    except LLMError as exc:
        logger.error("AI provider fail: %s", exc)
        return Reply(FALLBACK_ERROR, "error")

    record_usage(tenant, result.input_tokens, result.output_tokens)

    reply = interpret(result.text)
    if reply.flag == "":
        reply = _fix_script_once(provider, message, system, history, reply, tenant)
    reply.llm_ms = int((time.monotonic() - started) * 1000)
    return reply


def interpret(raw_text: str) -> Reply:
    """Model ke jawab me [[UNKNOWN]] ya [[HANDOVER]] dhoondhta hai aur final Reply banata hai."""
    text = (raw_text or "").strip()
    if HANDOVER_MARKER in text:
        return Reply(FALLBACK_HANDOVER, "handover")
    if UNKNOWN_MARKER in text:
        return Reply(FALLBACK_UNKNOWN, "unknown")
    if not text:
        return Reply(FALLBACK_ERROR, "error")
    return Reply(text[:MAX_REPLY_CHARS])


def _fix_script_once(provider, message, system, history, reply, tenant) -> Reply:
    """Lipi alag ho to ek baar dobara maango. Fail ho to pehla jawab hi rakho."""
    fix = script_fix_instruction(message.body, reply.text)
    if fix is None:
        return reply
    try:
        retry = provider.complete(
            system=f"{system}\n\n{fix}", messages=history, max_tokens=settings.LLM_MAX_OUTPUT_TOKENS
        )
    except LLMError as exc:
        logger.warning("script sudhaar ki dobara koshish fail: %s", exc)
        return reply
    record_usage(tenant, retry.input_tokens, retry.output_tokens)
    fixed = interpret(retry.text)
    if fixed.flag == "" and script_fix_instruction(message.body, fixed.text) is None:
        return fixed
    logger.warning("script sudhaar kaam nahi aaya, pehla jawab bheja")
    return reply
