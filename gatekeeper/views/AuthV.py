from django.views.generic import TemplateView
from django.contrib.auth import login as auth_login
from django.views.decorators.cache import never_cache
from django.utils.decorators import method_decorator
from django.shortcuts import render, redirect
import logging

from gatekeeper.forms import LoginForm, RegisterForm

logger = logging.getLogger('aegis')


@method_decorator(never_cache, name='dispatch')
class LoginView(TemplateView):
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
