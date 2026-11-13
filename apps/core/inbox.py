"""Owner ka simple inbox: jin chats me insaan ko jawab dena hai, unhe dekho aur reply bhejo."""

from django.contrib import messages as flash
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.whatsapp.client import WhatsAppError, mask_phone, send_text

from .models import Conversation, Message, Tenant

MAX_REPLY = 1000


def allowed_tenants(user):
    if user.is_superuser:
        return Tenant.objects.all()
    return Tenant.objects.filter(members=user)


def _conversations(user):
    return Conversation.objects.filter(tenant__in=allowed_tenants(user)).select_related(
        "customer", "tenant"
    )


@staff_member_required
def inbox(request):
    base = _conversations(request.user)
    needs_human = base.filter(state=Conversation.State.HUMAN).order_by("-last_message_at")
    # Jahan bot ko jawab nahi mila, wo bhi dikhao (owner ko seekhna hai kya add karna hai)
    flagged_ids = (
        Message.objects.filter(
            conversation__in=base,
            direction=Message.Direction.OUT,
            flag__in=["unknown", "error", "budget"],
        )
        .order_by("-id")
        .values_list("conversation_id", flat=True)[:50]
    )
    flagged = base.filter(pk__in=list(flagged_ids)).exclude(state=Conversation.State.HUMAN)
    recent = base.order_by("-last_message_at")[:30]
    for group in (needs_human, flagged, recent):
        for conv in group:
            conv.masked_phone = mask_phone(conv.customer.phone)
    return render(
        request,
        "inbox/list.html",
        {"needs_human": needs_human, "flagged": flagged, "recent": recent},
    )


@staff_member_required
@require_http_methods(["GET", "POST"])
def conversation_detail(request, pk):
    conv = _conversations(request.user).filter(pk=pk).first()
    if conv is None:
        raise Http404
    now = timezone.now()
    window_open = bool(conv.window_expires_at and conv.window_expires_at > now)

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "release":
            conv.state = Conversation.State.BOT
            conv.save(update_fields=["state"])
            flash.success(request, "Bot ko wapas de diya. Ab bot jawab dega.")
        elif action == "reply":
            body = request.POST.get("body", "").strip()[:MAX_REPLY]
            if not body:
                flash.error(request, "Khali message nahi bhej sakte.")
            elif not window_open:
                flash.error(
                    request,
                    "24 ghante ki window band hai. WhatsApp sirf approved template message "
                    "bhejne deta hai. Customer ke naye message ka wait karo.",
                )
            else:
                try:
                    wa_id = send_text(conv.tenant, conv.customer.phone, body)
                except WhatsAppError as exc:
                    flash.error(request, f"Message nahi gaya: {exc}")
                else:
                    Message.objects.create(
                        tenant=conv.tenant,
                        conversation=conv,
                        direction=Message.Direction.OUT,
                        type="text",
                        body=body,
                        wa_message_id=wa_id,
                        flag="owner",
                    )
                    if conv.state != Conversation.State.HUMAN:
                        conv.state = Conversation.State.HUMAN
                        conv.save(update_fields=["state"])
                    flash.success(request, "Bhej diya.")
        return redirect("inbox-detail", pk=conv.pk)

    thread = list(conv.messages.order_by("created_at", "id")[:200])
    return render(
        request,
        "inbox/detail.html",
        {"conv": conv, "thread": thread, "window_open": window_open},
    )
