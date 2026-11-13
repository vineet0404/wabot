import math
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.core.models import Message


def percentile(sorted_values: list[int], pct: float) -> int:
    """Nearest-rank percentile. Khali list par 0."""
    if not sorted_values:
        return 0
    index = max(0, min(len(sorted_values) - 1, math.ceil(pct / 100 * len(sorted_values)) - 1))
    return sorted_values[index]


class Command(BaseCommand):
    help = "Bot kitni jaldi jawab deta hai: p50/p95 (customer message se jawab bhejne tak)."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=7)
        parser.add_argument("--tenant", type=int)

    def handle(self, *args, **opts):
        rows = Message.objects.filter(
            direction=Message.Direction.OUT,
            total_ms__isnull=False,
            created_at__gte=timezone.now() - timedelta(days=opts["days"]),
        )
        if opts["tenant"]:
            rows = rows.filter(tenant_id=opts["tenant"])

        total = sorted(rows.values_list("total_ms", flat=True))
        llm = sorted(v for v in rows.values_list("llm_ms", flat=True) if v is not None)
        if not total:
            self.stdout.write("Abhi koi jawab record nahi hua.")
            return

        def line(name, values):
            if not values:
                return
            self.stdout.write(
                f"{name:<22} p50 {percentile(values, 50) / 1000:5.1f}s   "
                f"p95 {percentile(values, 95) / 1000:5.1f}s   max {values[-1] / 1000:5.1f}s"
            )

        self.stdout.write(f"Pichle {opts['days']} din, {len(total)} jawab:")
        line("Kul (message -> jawab)", total)
        line("Sirf AI ka time", llm)

        slow = sum(1 for v in total if v > 10_000)
        self.stdout.write(f"10 second se zyada: {slow}/{len(total)}")
        flagged = rows.exclude(flag="").values_list("flag", flat=True)
        counts: dict[str, int] = {}
        for flag in flagged:
            counts[flag] = counts.get(flag, 0) + 1
        if counts:
            self.stdout.write("Flags: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
        p95 = percentile(total, 95)
        if p95 > 10_000:
            self.stdout.write(
                "\n[FIX] p95 10 second se upar hai. Tez provider/chhota model lo, "
                "LLM_MAX_OUTPUT_TOKENS ghatao, ya history kam karo (docs/LATENCY.md)."
            )
