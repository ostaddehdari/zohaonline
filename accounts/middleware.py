from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse


class EnabledUserMiddleware:
    """Immediately terminates sessions for product-disabled accounts."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user and user.is_authenticated and not user.is_superuser and not getattr(user, 'is_enabled', True):
            logout(request)
            return redirect(f"{reverse('login')}?disabled=1")
        return self.get_response(request)
