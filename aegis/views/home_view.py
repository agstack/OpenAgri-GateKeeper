from django.views.generic import TemplateView


class HomeView(TemplateView):
    template_name = "index.html"
    permission_menu = ''

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context

