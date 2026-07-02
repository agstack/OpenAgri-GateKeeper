# views/auth_views.py

import requests

# from django import forms
from django.conf import settings
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.generic.edit import FormView

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from urllib.parse import urlencode, urlparse, urlunparse, parse_qs

from aegis.forms import UserLoginForm
from aegis.throttles import check_login_allowed, clear_login_failures, register_login_failure


@method_decorator(never_cache, name='dispatch')
class LoginView(FormView):
    template_name = "auth/login.html"
    form_class = UserLoginForm
    success_url = reverse_lazy('home')
    # success_url = reverse_lazy("aegis:dashboard")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["next"] = self.request.GET.get("next", "") or self.request.POST.get("next", "")
        return context

    def get(self, request, *args, **kwargs):
        form = self.form_class()
        context = self.get_context_data(form=form)
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        next_url = request.POST.get("next") or request.GET.get("next", "")

        if not next_url:
            return HttpResponseRedirect(self.success_url)

        form = self.form_class(request.POST)

        if form.is_valid():
            username = form.cleaned_data["username"]
            password = form.cleaned_data["password"]
            # service_name = form.cleaned_data["service_name"]

            allowed, retry_after = check_login_allowed(request, identifier=username)
            if not allowed:
                form.add_error(None, f"Too many login attempts. Try again in {retry_after} seconds.")
                return self.render_to_response(self.get_context_data(form=form))

            login_url = f"{settings.INTERNAL_GK_URL}api/login/"

            try:
                response = requests.post(
                    login_url,
                    data={"username": username, "password": password}
                )
            except requests.RequestException as e:
                form.add_error(None, f"Could not connect to Gatekeeper: {str(e)}")
                return self.render_to_response(self.get_context_data(form=form))

            if response.status_code == status.HTTP_200_OK:
                data = response.json()
                access_token = data["access"]
                refresh_token = data["refresh"]
                clear_login_failures(request, identifier=username)

                # Determine the redirect URL
                if next_url == "FarmCalendar":
                    next_url = settings.AVAILABLE_SERVICES.get(next_url, {}).get('post_auth')
                elif next_url == "IrrigationManagement":
                    next_url = settings.AVAILABLE_SERVICES.get(next_url, {}).get('post_auth')
                elif not next_url:
                    next_url = self.success_url

                # Parse and update the URL with the access token
                url_parts = list(urlparse(next_url))
                query = parse_qs(url_parts[4])  # Parse the existing query string

                query["access_token"] = access_token
                query["refresh_token"] = refresh_token
                url_parts[4] = urlencode(query, doseq=True)

                # Final redirect URL with tokens
                redirect_url = urlunparse(url_parts)

                return HttpResponseRedirect(redirect_url)

            else:
                if response.status_code in {status.HTTP_400_BAD_REQUEST, status.HTTP_401_UNAUTHORIZED, status.HTTP_429_TOO_MANY_REQUESTS}:
                    register_login_failure(request, identifier=username)
                form.add_error(None, "Invalid credentials")

        return self.render_to_response(self.get_context_data(form=form))


class WhoAmIView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        return Response({"user": str(request.user)}, status=200)
