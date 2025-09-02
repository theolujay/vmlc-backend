from django.apps import AppConfig
from typing import Any


class ApiConfig(AppConfig):
    default_auto_field: str = "django.db.models.BigAutoField"
    name: str = "api"

    def ready(self) -> None:
        import api.signals
