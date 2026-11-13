from django.core.management.base import BaseCommand

from apps.core.models import Tenant
from apps.knowledge.search import search


class Command(BaseCommand):
    help = "Dekho ki kisi sawal par knowledge base se kaun se chunks milte hain."

    def add_arguments(self, parser):
        parser.add_argument("query")
        parser.add_argument("--tenant", type=int, required=True)

    def handle(self, *args, **opts):
        tenant = Tenant.objects.get(pk=opts["tenant"])
        results = search(tenant, opts["query"])
        if not results:
            self.stdout.write("Kuch nahi mila.")
        for i, text in enumerate(results, 1):
            self.stdout.write(f"--- {i} ---\n{text}\n")
