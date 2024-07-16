# aegis/views/api/auth.py

from django.views.generic import TemplateView
from django.contrib.auth import authenticate, login as auth_login
from django.contrib.auth import authenticate
from django.views.decorators.cache import never_cache
from django.utils.decorators import method_decorator
from django.shortcuts import render, redirect

from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import logging

from gatekeeper.forms import LoginForm

logger = logging.getLogger('aegis')


@method_decorator(never_cache, name='dispatch')
class LoginV(TemplateView):
    template_name = "auth/login.html"

    def get(self, request, *args, **kwargs):
        logger.info("LoginV view accessed")
        form = LoginForm()
        context = self.get_context_data(**kwargs)
        context['form'] = form
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)
            return redirect('home')  # Redirect to a success page.
        context = self.get_context_data(**kwargs)
        context['form'] = form
        return render(request, self.template_name, context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


class TokenObtainView(APIView):
    def post(self, request, *args, **kwargs):
        username = request.data.get('username')
        password = request.data.get('password')
        user = authenticate(username=username, password=password)

        if user is not None:
            refresh = RefreshToken.for_user(user)
            logger.info(f"Generated tokens for user: {username}")
            return Response({
                'refresh_token': str(refresh),
                'access_token': str(refresh.access_token),
            })
        else:
            return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)


class CustomTokenRefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        logger.info(f"Refreshed token: {response.data.get('access_token')}")
        return response
