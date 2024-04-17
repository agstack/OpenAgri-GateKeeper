from django.apps import AppConfig


class AegisConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'aegis'
    verbose_name = 'Auth'

    def ready(self):
        import aegis.signals

