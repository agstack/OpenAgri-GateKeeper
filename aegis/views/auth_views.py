# views/auth_views.py

import requests

from django import forms
from django.conf import settings
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.generic.edit import FormView

from rest_framework import status
from urllib.parse import urlencode, urlparse, urlunparse, parse_qs

from aegis.forms import UserRegistrationForm, UserLoginForm
from aegis.services.auth_services import register_user


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

            login_url = f"{settings.INTERNAL_GK_URL}api/login/"

            # Use the same authentication endpoint used by LoginAPIView to obtain tokens
            # response = requests.post(
            #     # request.build_absolute_uri(reverse_lazy('api_login')),
            #     f"http://gatekeeper:8001/api/login/",  # Internal service URL
            #     data={"username": username, "password": password}
            # )

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
                query["refresh"] = refresh_token
                url_parts[4] = urlencode(query, doseq=True)

                # Final redirect URL with tokens
                redirect_url = urlunparse(url_parts)

                return HttpResponseRedirect(redirect_url)

            else:
                form.add_error(None, "Invalid credentials")

        return self.render_to_response(self.get_context_data(form=form))


# @method_decorator(never_cache, name='dispatch')
# class RegisterView(FormView):
#     template_name = "auth/register.html"
#     form_class = UserRegistrationForm
#     success_url = reverse_lazy("login")
#
#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         context["next"] = self.request.GET.get("next", "") or self.request.POST.get("next", "")
#         return context
#
#     def get(self, request, *args, **kwargs):
#         form = self.form_class()
#         context = self.get_context_data(form=form)
#         return self.render_to_response(context)
#
#     def post(self, request, *args, **kwargs):
#         next_url = request.POST.get("next") or request.GET.get("next", "")
#         form = self.form_class(request.POST)
#
#         if form.is_valid():
#             try:
#                 # Register the user
#                 register_user(
#                     username=form.cleaned_data["username"],
#                     email=form.cleaned_data["email"],
#                     password=form.cleaned_data["password"],
#                     first_name=form.cleaned_data["first_name"],
#                     last_name=form.cleaned_data["last_name"],
#                     # service_name=form.cleaned_data["service_name"],
#                 )
#
#                 if next_url:
#                     redirect_url = f"{reverse_lazy('login')}?next={next_url}"
#                 else:
#                     redirect_url = reverse_lazy("login")
#
#                 return HttpResponseRedirect(redirect_url)
#
#             except forms.ValidationError as e:
#                 form.add_error(None, str(e))
#             except Exception as e:
#                 form.add_error(None, f"An unexpected error occurred: {str(e)}")
#
#         return self.render_to_response(self.get_context_data(form=form))
