import logging

from django.conf import settings
from django.utils import timezone

from apps.core.models import Message

from .prompt_template import SYSTEM_TEMPLATE

logger = logging.getLogger(__name__)

MAX_CHARS = 1000


def knowledge_for(tenant, question: str) -> str:
    """Knowledge base se sawal se jude tukde. Kuch bhi bigde to khali (jawab phir bhi jata hai)."""
    try:
        from apps.knowledge.search import search

        return "\n\n".join(search(tenant, question))
    except Exception:
        logger.exception("knowledge search fail, uske bina aage badh rahe hain")
        return ""


def build_system_prompt(tenant, question: str = "") -> str:
    now = timezone.localtime()
    info = tenant.business_info.strip()
    extra = knowledge_for(tenant, question) if question else ""
    if extra:
        info = f"{info}\n\nMORE DETAILS (from the business's documents):\n{extra}".strip()
    return SYSTEM_TEMPLATE.format(
        name=tenant.name,
        business_type=tenant.get_business_type_display().lower(),
        today=now.strftime("%d %B %Y"),
        weekday=now.strftime("%A"),
        tz=tenant.timezone,
        info=info or "(no information provided yet)",
    )


def build_messages(message: Message) -> list[dict]:
    """Is conversation ke pichle kuch messages, provider ke format me.

    Lagataar same-role messages jod diye jaate hain, aur list hamesha user se shuru hoti hai.
    """
    rows = list(
        Message.objects.filter(conversation=message.conversation, id__lte=message.pk)
        .exclude(body="")
        .order_by("-id")[: settings.LLM_HISTORY_MESSAGES]
    )
    rows.reverse()

    turns: list[dict] = []
    for row in rows:
        role = "user" if row.direction == Message.Direction.IN else "assistant"
        content = row.body[:MAX_CHARS]
        if turns and turns[-1]["role"] == role:
            turns[-1]["content"] += "\n" + content
        else:
            turns.append({"role": role, "content": content})
    while turns and turns[0]["role"] != "user":
        turns.pop(0)
    return turns


def recent_user_text(message: Message) -> str:
    """Retrieval ke liye sawal: customer ke aakhri 2 messages (follow-up samajhne ke liye)."""
    rows = (
        Message.objects.filter(
            conversation=message.conversation, direction=Message.Direction.IN, id__lte=message.pk
        )
        .exclude(body="")
        .order_by("-id")[:2]
    )
    return "\n".join(r.body[:MAX_CHARS] for r in reversed(list(rows)))
