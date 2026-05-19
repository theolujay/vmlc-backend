from django.apps import AppConfig


class CompetitionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "competition"

    def ready(self) -> None:
        import competition.signals
