from django.conf import settings
from django.db import models

from .fields import EncryptedTextField


class Tenant(models.Model):
    """Ek business (clinic, salon, hospital). Baaki saari tables isse judti hain."""

    class BusinessType(models.TextChoices):
        CLINIC = "clinic", "Clinic"
        HOSPITAL = "hospital", "Hospital"
        SALON = "salon", "Salon"
        RESTAURANT = "restaurant", "Restaurant"
        COACHING = "coaching", "Coaching class"
        OTHER = "other", "Other"

    name = models.CharField(max_length=120)
    business_type = models.CharField(
        max_length=20, choices=BusinessType.choices, default=BusinessType.CLINIC
    )
    wa_phone_number_id = models.CharField(
        max_length=64,
        unique=True,
        help_text="Meta dashboard, WhatsApp, API Setup me 'Phone number ID'.",
    )
    wa_access_token = EncryptedTextField(
        blank=True,
        help_text="Database me encrypted rehta hai. Admin form me dobara nahi dikhta.",
    )
    timezone = models.CharField(max_length=64, default="Asia/Kolkata")
    language = models.CharField(max_length=20, default="hinglish")
    business_info = models.TextField(
        blank=True,
        help_text=(
            "Timing, services, prices, address, FAQs likho (saada text). "
            "Bot sirf isi se jawab dega. "
            "Hafta 3 me ye knowledge base se badal jayega."
        ),
    )
    is_active = models.BooleanField(default=True)

    # Owner ko notification (docs/BOOKING_AND_REMINDERS.md). Dono khali = notification nahi.
    notify_email = models.EmailField(
        blank=True, help_text="Handover/booking par email yahan jayegi."
    )
    notify_telegram_chat_id = models.CharField(
        max_length=40, blank=True, help_text="Owner ka Telegram chat id (bot se baat shuru karke)."
    )

    # Booking aur reminders
    slot_minutes = models.PositiveSmallIntegerField(
        default=30, help_text="Ek appointment kitne minute ka. Isse takraav (clash) dikhta hai."
    )
    reminder_hours_before = models.PositiveSmallIntegerField(
        default=3, help_text="Appointment se kitne ghante pehle yaad dilana. 0 = reminder band."
    )
    template_lang = models.CharField(
        max_length=10, default="en", help_text="Meta me template ki language ka code (en, hi...)."
    )
    confirm_template = models.CharField(
        max_length=80,
        blank=True,
        help_text="24 ghante baad confirm bhejne ka approved template ka naam (optional).",
    )
    reminder_template = models.CharField(
        max_length=80,
        blank=True,
        help_text="Reminder ke liye approved template ka naam. Khali = sirf 24 ghante ke andar.",
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="wabot_tenants",
        help_text="Jo staff users is business ka inbox dekh aur jawab de sakte hain.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Customer(models.Model):
    """Patient ya customer. Sirf naam, number aur bhasha. Health ki details kabhi nahi."""

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="customers")
    phone = models.CharField(max_length=20)
    name = models.CharField(max_length=120, blank=True)
    language = models.CharField(max_length=20, blank=True)
    consent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "phone"], name="uniq_customer_per_tenant")
        ]

    def __str__(self):
        return self.name or self.phone


class Conversation(models.Model):
    class State(models.TextChoices):
        BOT = "bot", "Bot chalu"
        HUMAN = "human", "Owner sambhal raha hai"

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="conversations")
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="conversations")
    channel = models.CharField(max_length=20, default="whatsapp")
    state = models.CharField(max_length=10, choices=State.choices, default=State.BOT)
    last_message_at = models.DateTimeField(null=True, blank=True)
    window_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Customer ke aakhri message ke 24 ghante baad tak free reply.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "customer", "channel"], name="uniq_conversation_per_customer"
            )
        ]

    def __str__(self):
        return f"{self.tenant} / {self.customer}"


class Message(models.Model):
    class Direction(models.TextChoices):
        IN = "in", "Customer se"
        OUT = "out", "Bot ya owner se"

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="messages")
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    direction = models.CharField(max_length=3, choices=Direction.choices)
    type = models.CharField(max_length=20, default="text")
    body = models.TextField(blank=True)
    wa_message_id = models.CharField(
        max_length=128,
        null=True,
        blank=True,
        unique=True,
        help_text="Meta ka message id. Unique hai, isse dobara aaya message rukta hai.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    flag = models.CharField(
        max_length=20,
        blank=True,
        default="",
        help_text="unknown = bot ko jawab nahi mila, handover = owner ko dena hai, "
        "error/budget = AI chala nahi.",
    )
    reply_to = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="replies"
    )
    llm_ms = models.PositiveIntegerField(
        null=True, blank=True, help_text="AI ko jawab banane me kitne millisecond lage."
    )
    total_ms = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Customer ka message aane se jawab bhejne tak kul millisecond.",
    )

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["conversation", "created_at"])]

    def __str__(self):
        return f"{self.direction} {self.type} #{self.pk}"


class LLMUsage(models.Model):
    """Har business ka roz ka AI kharch (tokens me), daily limit ke liye."""

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="llm_usage")
    date = models.DateField()
    calls = models.PositiveIntegerField(default=0)
    input_tokens = models.BigIntegerField(default=0)
    output_tokens = models.BigIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "date"], name="uniq_usage_per_tenant_day")
        ]

    def __str__(self):
        return f"{self.tenant} {self.date}"
