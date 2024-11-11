# views/auth_views.py

from django import forms
from django.conf import settings
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.generic.edit import FormView

from urllib.parse import urlencode, urlparse, urlunparse, parse_qs

from aegis.forms import UserRegistrationForm, UserLoginForm
from aegis.services.auth_services import register_user, authenticate_user


@method_decorator(never_cache, name='dispatch')
class LoginView(FormView):
    template_name = "auth/login.html"
    form_class = UserLoginForm
    success_url = reverse_lazy("dashboard")

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
        form = self.form_class(request.POST)

        if form.is_valid():
            username = form.cleaned_data["username"]
            password = form.cleaned_data["password"]

            # Authenticate the user
            user, access_token, refresh_token = authenticate_user(username, password)
            if user:
                if next_url == "FarmCalendar":
                    next_url = settings.AVAILABLE_SERVICES.get(next_url, {}).get('post_auth')
                elif not next_url:
                    next_url = self.success_url

                # Parse and update the URL with the access token
                url_parts = list(urlparse(next_url))
                query = parse_qs(url_parts[4])  # Parse the existing query string

                query["access_token"] = access_token
                url_parts[4] = urlencode(query, doseq=True)

                # Final redirect URL with tokens
                redirect_url = urlunparse(url_parts)

                return HttpResponseRedirect(redirect_url)
            else:
                form.add_error(None, "Invalid credentials")

        return self.render_to_response(self.get_context_data(form=form))


@method_decorator(never_cache, name='dispatch')
class RegisterView(FormView):
    template_name = "auth/register.html"
    form_class = UserRegistrationForm
    success_url = reverse_lazy("login")

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
        form = self.form_class(request.POST)

        if form.is_valid():
            try:
                # Register the user
                register_user(
                    username=form.cleaned_data["username"],
                    email=form.cleaned_data["email"],
                    password=form.cleaned_data["password"],
                    # contact_no=form.cleaned_data["contact_no"],
                    first_name=form.cleaned_data["first_name"],
                    last_name=form.cleaned_data["last_name"]
                )

                if next_url:
                    redirect_url = f"{reverse_lazy('login')}?next={next_url}"
                else:
                    redirect_url = reverse_lazy("login")

                return HttpResponseRedirect(redirect_url)

            except forms.ValidationError as e:
                form.add_error(None, str(e))

        return self.render_to_response(self.get_context_data(form=form))
