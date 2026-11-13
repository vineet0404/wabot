from django.conf import settings
from django.db.models import F
from django.utils import timezone

from apps.core.models import LLMUsage


def tokens_used_today(tenant) -> int:
    row = LLMUsage.objects.filter(tenant=tenant, date=timezone.localdate()).first()
    return (row.input_tokens + row.output_tokens) if row else 0


def budget_exceeded(tenant) -> bool:
    budget = settings.LLM_DAILY_TOKEN_BUDGET
    return budget > 0 and tokens_used_today(tenant) >= budget


def record_usage(tenant, input_tokens: int, output_tokens: int) -> None:
    usage, _ = LLMUsage.objects.get_or_create(tenant=tenant, date=timezone.localdate())
    LLMUsage.objects.filter(pk=usage.pk).update(
        calls=F("calls") + 1,
        input_tokens=F("input_tokens") + input_tokens,
        output_tokens=F("output_tokens") + output_tokens,
    )
