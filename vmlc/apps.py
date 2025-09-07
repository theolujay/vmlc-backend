from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field: str = "django.db.models.BigAutoField"
    name = "vmlc"

    def ready(self) -> None:
        import vmlc.signals
