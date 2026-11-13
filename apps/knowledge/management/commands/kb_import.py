from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.core.models import Tenant
from apps.knowledge.models import KnowledgeDoc
from apps.knowledge.service import reindex


class Command(BaseCommand):
    help = "Text file ko knowledge base me daalta hai. Same title par purana badal jata hai."

    def add_arguments(self, parser):
        parser.add_argument("file")
        parser.add_argument("--tenant", type=int, required=True)
        parser.add_argument("--title", help="Default: file ka naam")

    def handle(self, *args, **opts):
        path = Path(opts["file"])
        if not path.is_file():
            raise CommandError(f"File nahi mili: {path}")
        try:
            tenant = Tenant.objects.get(pk=opts["tenant"])
        except Tenant.DoesNotExist as exc:
            raise CommandError("Is id ka tenant nahi hai") from exc
        title = opts["title"] or path.stem
        doc, _ = KnowledgeDoc.objects.update_or_create(
            tenant=tenant,
            title=title,
            defaults={"content": path.read_text(encoding="utf-8"), "is_active": True},
        )
        count = reindex(doc)
        self.stdout.write(self.style.SUCCESS(f"'{title}' save hua, {count} chunks."))
