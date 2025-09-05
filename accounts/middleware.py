from django.http import HttpResponseForbidden
from axes.models import AccessAttempt

class BlockIPMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ip = request.META.get('REMOTE_ADDR')
        if AccessAttempt.objects.filter(ip_address=ip, failures_since_start__gte=5).exists():
            return HttpResponseForbidden("Access denied: Your IP is blocked.")
        return self.get_response(request)