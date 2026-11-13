from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse


def health(request):
    return JsonResponse({"status": "ok"})


def ready(request):
    """Gehra check: database aur cache (Redis) dono chal rahe hain? Uptime monitor isse dekhe."""
    problems = []
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        problems.append("database")
    try:
        cache.set("ready-check", "1", 10)
        if cache.get("ready-check") != "1":
            problems.append("cache")
    except Exception:
        problems.append("cache")
    if problems:
        return JsonResponse({"status": "dikkat", "problems": problems}, status=503)
    return JsonResponse({"status": "ok"})


def home(request):
    return JsonResponse(
        {
            "app": "wabot",
            "status": "chal raha hai",
            "links": {
                "admin": "/admin/",
                "health": "/health/",
                "inbox": "/inbox/",
                "webhook": "/webhooks/whatsapp/",
            },
        }
    )
