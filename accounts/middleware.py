from django.http import HttpResponseForbidden
from axes.models import AccessAttempt
from django.shortcuts import redirect
from django.urls import reverse
from urllib.parse import urlparse, parse_qs

class AdminLoginRedirectMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if response.status_code == 302 and 'Location' in response:
            location = response['Location']
            if '/accounts/login/' in location:
                parsed = urlparse(location)
                query = parse_qs(parsed.query)
                next_url = query.get('next', [''])[0]
                if next_url.startswith('/securelogin/'):
                    return redirect(f'{reverse("admin:login")}?next={next_url}')
        return response


class BlockIPMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ip = request.META.get('REMOTE_ADDR')
        if AccessAttempt.objects.filter(ip_address=ip, failures_since_start__gte=5).exists():
            return HttpResponseForbidden("Access denied: Your IP is blocked.")
        return self.get_response(request)