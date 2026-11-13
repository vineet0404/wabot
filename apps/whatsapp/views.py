import hmac
import json
import logging

from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from apps.core.ratelimit import add_failure, client_ip, count

from .services import process_payload
from .signature import verify_signature
from .tasks import handle_inbound_message

logger = logging.getLogger(__name__)

BAD_SIGNATURE_LIMIT = 20
BAD_SIGNATURE_WINDOW = 10 * 60


@csrf_exempt
@require_http_methods(["GET", "POST"])
def webhook(request):
    if request.method == "GET":
        return _verify(request)
    return _receive(request)


def _verify(request):
    """Meta webhook jodte waqt ye GET bhejta hai."""
    mode = request.GET.get("hub.mode")
    token = request.GET.get("hub.verify_token") or ""
    challenge = request.GET.get("hub.challenge", "")
    expected = settings.META_VERIFY_TOKEN
    if mode == "subscribe" and expected and hmac.compare_digest(token, expected):
        return HttpResponse(challenge, content_type="text/plain")
    return HttpResponseForbidden("verify token galat hai")


def _receive(request):
    ip = client_ip(request)
    fail_key = f"badsig:{ip}"
    if count(fail_key) >= BAD_SIGNATURE_LIMIT:
        return HttpResponse("bahut zyada galat requests", status=429)

    body = request.body
    signature = request.headers.get("X-Hub-Signature-256")
    if not verify_signature(settings.META_APP_SECRET, body, signature):
        add_failure(fail_key, BAD_SIGNATURE_WINDOW)
        logger.warning("webhook: galat signature ip=%s", ip)
        return HttpResponse("signature galat hai", status=401)

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest("json galat hai")

    for message_id in process_payload(payload):
        handle_inbound_message.delay(message_id)

    # Meta ko hamesha jaldi 200 chahiye, warna wo dobara bhejta rehta hai.
    return HttpResponse("ok")
