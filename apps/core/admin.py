from django import forms
from django.contrib import admin

from .models import Conversation, Customer, LLMUsage, Message, Tenant


class TenantForm(forms.ModelForm):
    # Token screen par dobara kabhi nahi dikhta. Khali chhodo to purana token rehta hai.
    wa_access_token = forms.CharField(
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text="Naya token daalo. Khali chhodoge to purana token waisa hi rahega.",
    )

    class Meta:
        model = Tenant
        fields = (
            "name",
            "business_type",
            "wa_phone_number_id",
            "wa_access_token",
            "timezone",
            "language",
            "business_info",
            "members",
            "notify_email",
            "notify_telegram_chat_id",
            "slot_minutes",
            "reminder_hours_before",
            "template_lang",
            "confirm_template",
            "reminder_template",
            "is_active",
        )

    def clean_wa_access_token(self):
        value = self.cleaned_data.get("wa_access_token", "").strip()
        if not value and self.instance.pk:
            return self.instance.wa_access_token
        return value


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    form = TenantForm
    list_display = ("name", "business_type", "wa_phone_number_id", "is_active", "created_at")
    list_filter = ("business_type", "is_active")
    search_fields = ("name", "wa_phone_number_id")
    filter_horizontal = ("members",)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("phone", "name", "tenant", "created_at")
    list_filter = ("tenant",)
    search_fields = ("phone", "name")


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("customer", "tenant", "state", "last_message_at")
    list_filter = ("tenant", "state")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "tenant", "direction", "type", "flag", "total_ms", "created_at")
    list_filter = ("tenant", "direction", "type", "flag")


@admin.register(LLMUsage)
class LLMUsageAdmin(admin.ModelAdmin):
    list_display = ("tenant", "date", "calls", "input_tokens", "output_tokens")
    list_filter = ("tenant",)
