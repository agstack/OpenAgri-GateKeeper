# middleware.py

from django.shortcuts import redirect

from rest_framework_simplejwt.tokens import AccessToken


def jwt_middleware(get_response):
    def middleware(request):
        access_token = request.COOKIES.get('access_token')
        try:
            AccessToken(access_token)  # Validates the access token
        except:
            return redirect('login')
        return get_response(request)
    return middleware
