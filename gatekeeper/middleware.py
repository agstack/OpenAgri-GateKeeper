# middleware.py

from django.http import JsonResponse
from django.shortcuts import redirect
from urllib.parse import urlencode

from rest_framework_simplejwt.tokens import AccessToken


def jwt_middleware(get_response):
    def middleware(request):
        access_token = request.GET.get('access_token')
        next_param = request.GET.get('next')

        # Check for access_token presence
        if not access_token:
            if next_param:
                login_url = f"http://127.0.0.1:8001/login/?{urlencode({'next': next_param})}"
            else:
                login_url = '/login'
            return redirect(login_url)

        try:
            AccessToken(access_token)
        except Exception as e:
            return JsonResponse({"error": "Invalid or expired token"}, status=401)

        return get_response(request)
    return middleware
