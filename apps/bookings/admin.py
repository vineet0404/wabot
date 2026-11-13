from django.contrib import admin

from .models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("display_name", "tenant", "starts_at", "status", "reminder_sent_at")
    list_filter = ("tenant", "status")
    search_fields = ("name", "customer__phone")
