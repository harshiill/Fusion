from django.apps import AppConfig


class HealthCenterConfig(AppConfig):
    name = 'applications.health_center'

    def ready(self):
        import applications.health_center.signals  # noqa: F401
