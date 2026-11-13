from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.bookings.reminders import due_bookings, send_due_reminders


class Command(BaseCommand):
    help = (
        "Jinka reminder ka samay aa gaya unko abhi bhejta hai (beat ke bina haath se test ke liye)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Sirf dikhao, bhejo mat")

    def handle(self, *args, **opts):
        if opts["dry_run"]:
            rows = due_bookings(timezone.now())
            for b in rows:
                self.stdout.write(f"  {b.tenant.name}: {b.display_name} - {b.when_text()}")
            self.stdout.write(f"{len(rows)} reminder due hain (bheje nahi).")
            return
        self.stdout.write(f"Natija: {send_due_reminders()}")
