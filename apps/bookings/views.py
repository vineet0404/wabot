from django.contrib import messages as flash
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.inbox import allowed_tenants
from apps.whatsapp.client import mask_phone

from .models import Booking
from .service import (
    DRY_RUN,
    NOT_SENT,
    cancel_booking,
    confirm_booking,
    reject_booking,
)


def _scoped(user):
    return Booking.objects.filter(tenant__in=allowed_tenants(user)).select_related(
        "customer", "tenant", "conversation"
    )


def _decorate(rows):
    rows = list(rows)
    for b in rows:
        b.masked_phone = mask_phone(b.customer.phone)
        b.when = b.when_text()
        b.clash_list = list(b.clashes()) if b.status == Booking.Status.REQUESTED else []
    return rows


@staff_member_required
def bookings_list(request):
    base = _scoped(request.user)
    now = timezone.now()
    requested = base.filter(status=Booking.Status.REQUESTED, starts_at__gte=now)
    upcoming = base.filter(status=Booking.Status.CONFIRMED, starts_at__gte=now)
    past = base.exclude(pk__in=requested).exclude(pk__in=upcoming).order_by("-starts_at")[:20]
    return render(
        request,
        "bookings/list.html",
        {
            "requested": _decorate(requested),
            "upcoming": _decorate(upcoming),
            "past": _decorate(past),
        },
    )


@staff_member_required
@require_POST
def booking_action(request, pk):
    booking = _scoped(request.user).filter(pk=pk).first()
    if booking is None:
        raise Http404
    action = request.POST.get("action")
    if action == "confirm" and booking.status == Booking.Status.REQUESTED:
        result = confirm_booking(booking)
        if result == NOT_SENT:
            flash.warning(
                request,
                "Confirm ho gaya, par customer ko message nahi gaya (24 ghante ki window band "
                "hai aur confirm template set nahi). Customer ko khud batao.",
            )
        elif result == DRY_RUN:
            flash.warning(
                request,
                "Confirm ho gaya. Test mode: WhatsApp token nahi hai, isliye customer ko asli "
                "message nahi gaya (sirf log me).",
            )
        else:
            flash.success(request, "Confirm ho gaya, customer ko bata diya.")
    elif action == "reject" and booking.status == Booking.Status.REQUESTED:
        result = reject_booking(booking)
        flash.success(
            request,
            "Mana kar diya, customer ko bata diya."
            if result == "sent"
            else "Mana kar diya (customer ko asli message nahi gaya).",
        )
    elif action == "cancel" and booking.status == Booking.Status.CONFIRMED:
        cancel_booking(booking)
        flash.success(request, "Cancel kar diya. Customer ko khud bata dena.")
    else:
        flash.error(request, "Ye abhi nahi ho sakta.")
    return redirect("bookings")
