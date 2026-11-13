from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from apps.bookings import views as booking_views
from apps.core import inbox as inbox_views
from apps.core.views import health, home, ready

urlpatterns = [
    path("", home),
    path(settings.ADMIN_URL, admin.site.urls),
    path("health/", health),
    path("ready/", ready),
    path("inbox/", inbox_views.inbox, name="inbox"),
    path("inbox/bookings/", booking_views.bookings_list, name="bookings"),
    path("inbox/bookings/<int:pk>/", booking_views.booking_action, name="booking-action"),
    path("inbox/<int:pk>/", inbox_views.conversation_detail, name="inbox-detail"),
    path("webhooks/whatsapp/", include("apps.whatsapp.urls")),
]
