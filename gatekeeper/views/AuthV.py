from django.views.generic import TemplateView
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.views.decorators.cache import never_cache
from django.utils.decorators import method_decorator
from django.shortcuts import render, redirect
from django.urls import reverse, resolve, Resolver404
import logging

from gatekeeper.forms import LoginForm, RegisterForm, PasswordResetForm
from aegis.models import DefaultAuthUserExtend

logger = logging.getLogger('aegis')


@method_decorator(never_cache, name='dispatch')
class LoginView(TemplateView):
    template_name = "auth/login.html"

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            next_url = request.session.get('next', '')
            if next_url:
                return redirect(next_url)
            return redirect('aegis:dashboard')

        next_url = request.GET.get('next', '')
        if next_url:
            request.session['next'] = next_url

        logger.info("Login view accessed")
        form = LoginForm(initial={'next': next_url})
        context = self.get_context_data(**kwargs)
        context['form'] = form
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        form = LoginForm(request, data=request.POST)
        next_url = request.session.get('next', '')
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)
            if next_url:
                del request.session['next']  # Clear the next URL from session after successful login
                if self.is_valid_url(next_url):
                    return redirect(next_url)
                elif 'farm_calendar' in next_url:
                    return redirect('http://127.0.0.1:8002')
            return redirect('aegis:dashboard')
        context = self.get_context_data(**kwargs)
        context['form'] = form
        context['next'] = next_url
        return render(request, self.template_name, context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context

    def is_valid_url(self, url):
        """
        Check if the URL is valid and can be resolved to a view.
        """
        try:
            resolve(url)
            return True
        except Resolver404:
            return False


@method_decorator(never_cache, name='dispatch')
class RegisterView(TemplateView):
    form_class = RegisterForm
    template_name = 'auth/register.html'

    def get(self, request, *args, **kwargs):
        form = self.form_class()
        context = self.get_context_data(**kwargs)
        context['form'] = form
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        form = self.form_class(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            return redirect('home')  # Redirect to a success page.
        context = self.get_context_data(**kwargs)
        context['form'] = form
        return render(request, self.template_name, context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


@method_decorator(never_cache, name='dispatch')
class PasswordResetView(TemplateView):
    template_name = 'auth/password_reset.html'
    form_class = PasswordResetForm

    def get(self, request, *args, **kwargs):
        form = self.form_class()
        context = self.get_context_data(**kwargs)
        context['form'] = form
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        form = self.form_class(request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('email')
            new_password = form.cleaned_data.get('new_password1')
            try:
                user = DefaultAuthUserExtend.objects.get(email=email)
                user.set_password(new_password)
                user.save()
                logger.info("Password reset for user with email: {}".format(email))
                auth_login(request, user)
                return redirect('home')
            except DefaultAuthUserExtend.DoesNotExist:
                form.add_error('email', 'Email address not found.')

        context = self.get_context_data(**kwargs)
        context['form'] = form
        return render(request, self.template_name, context)

