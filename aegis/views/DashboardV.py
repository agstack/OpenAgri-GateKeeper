from django.contrib.auth.mixins import LoginRequiredMixin
from .mixins import AdminMenuMixin
from django.views.generic import TemplateView


class DashboardView(LoginRequiredMixin, TemplateView, AdminMenuMixin):
    template_name = "dashboard.html"
    permission_menu = ''

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context

