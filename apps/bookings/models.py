from datetime import timedelta
from zoneinfo import ZoneInfo

from django.db import models
from django.utils import timezone

from apps.core.models import Conversation, Customer, Message, Tenant


class Booking(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Maanga hai (owner ko confirm karna hai)"
        CONFIRMED = "confirmed", "Confirm"
        REJECTED = "rejected", "Mana kiya"
        CANCELLED = "cancelled", "Cancel"

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="bookings")
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="bookings")
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="bookings"
    )
    name = models.CharField(max_length=120, blank=True)
    service = models.CharField(max_length=120, blank=True)
    starts_at = models.DateTimeField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.REQUESTED)
    source_message = models.ForeignKey(
        Message, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    reminder_sent_at = models.DateTimeField(null=True, blank=True)
    reminder_result = models.CharField(
        max_length=12,
        blank=True,
        help_text="sent = gaya, skipped = window band aur template nahi (owner ko batana padega).",
    )

    class Meta:
        ordering = ["starts_at"]
        indexes = [models.Index(fields=["tenant", "status", "starts_at"])]

    def __str__(self):
        return f"{self.display_name} {self.starts_at:%d %b %H:%M}"

    @property
    def display_name(self) -> str:
        return self.name or self.customer.name or self.customer.phone

    def local_start(self):
        return timezone.localtime(self.starts_at, ZoneInfo(self.tenant.timezone))

    def when_text(self) -> str:
        """Customer/owner ko dikhane layak: 'Sunday, 8 Nov, 5:00 PM'."""
        t = self.local_start()
        return f"{t:%A}, {t.day} {t:%b}, {t.hour % 12 or 12}:{t:%M} {t:%p}"

    def clashes(self):
        """Isi business ke doosre confirm appointments jo is slot se takrate hain."""
        gap = timedelta(minutes=self.tenant.slot_minutes)
        return (
            Booking.objects.filter(
                tenant=self.tenant,
                status=self.Status.CONFIRMED,
                starts_at__gt=self.starts_at - gap,
                starts_at__lt=self.starts_at + gap,
            )
            .exclude(pk=self.pk)
            .select_related("customer")
        )
