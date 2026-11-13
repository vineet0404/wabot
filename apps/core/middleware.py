from django.conf import settings
from django.http import HttpResponse

from .ratelimit import client_ip, count

LOGIN_WINDOW = 15 * 60
MAX_FAILS_PER_IP = 10
MAX_FAILS_PER_USER = 5


def ip_key(ip: str) -> str:
    return f"loginfail:ip:{ip}"


def user_key(username: str) -> str:
    return f"loginfail:user:{username.lower()[:150]}"


class AdminLoginThrottleMiddleware:
    """Admin login par galat password ki bar-bar koshish ko 15 minute ke liye rokta hai."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.login_path = f"/{settings.ADMIN_URL}login/"

    def __call__(self, request):
        if request.method == "POST" and request.path == self.login_path:
            username = request.POST.get("username", "")
            if (
                count(ip_key(client_ip(request))) >= MAX_FAILS_PER_IP
                or count(user_key(username)) >= MAX_FAILS_PER_USER
            ):
                return HttpResponse(
                    "Bahut zyada galat koshish. 15 minute baad dobara try karo.", status=429
                )
        return self.get_response(request)
