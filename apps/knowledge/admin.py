from django.contrib import admin, messages

from .models import KnowledgeDoc
from .service import reindex


@admin.register(KnowledgeDoc)
class KnowledgeDocAdmin(admin.ModelAdmin):
    list_display = ("title", "tenant", "is_active", "updated_at")
    list_filter = ("tenant", "is_active")
    search_fields = ("title", "content")
    fields = ("tenant", "title", "content", "is_active")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        count = reindex(obj)
        self.message_user(request, f"{count} tukde (chunks) ban gaye.", messages.SUCCESS)
